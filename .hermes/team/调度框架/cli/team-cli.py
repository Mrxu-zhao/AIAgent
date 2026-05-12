#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
团队调度框架 CLI 工具
提供增强的命令行交互界面
"""

import sys
import os
import json
import argparse
from typing import Optional
from datetime import datetime

# 添加 core 模块路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import (
    get_router, get_bus, get_monitor, get_recovery_manager,
    TaskPriority, MessageType, MessagePriority
)

class Colors:
    """终端颜色"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class TeamCLI:
    """团队调度命令行界面"""
    
    def __init__(self):
        self.router = get_router()
        self.bus = get_bus()
        self.monitor = get_monitor()
        self.recovery = get_recovery_manager(self.router)
        if not self.monitor._running:
            self.monitor.start()
        
        # 注册所有Agent到消息总线
        for agent_id in self.router.agents:
            self.bus.register_agent(agent_id)
    
    def print_banner(self):
        """打印横幅"""
        print(f"{Colors.CYAN}")
        print("╔═══════════════════════════════════════════════════════════╗")
        print("║                                                           ║")
        print("║     AI Agent 团队调度框架 v2.0                            ║")
        print("║                                                           ║")
        print("║     智能路由 · 负载均衡 · 故障恢复 · 实时监控              ║")
        print("║                                                           ║")
        print("╚═══════════════════════════════════════════════════════════╝")
        print(f"{Colors.NC}")
    
    def cmd_status(self, args):
        """查看团队状态"""
        print(f"\n{Colors.BOLD}=== 团队状态 ==={Colors.NC}\n")
        
        # Agent状态
        print(f"{Colors.BOLD}Agent 状态:{Colors.NC}")
        print(f"{'Agent':<20} {'角色':<12} {'负载':<10} {'成功率':<8} {'状态'}")
        print("-" * 70)
        
        for agent_id, status in self.router.get_agent_status().items():
            color = Colors.GREEN if "空闲" in status['status'] else \
                    Colors.YELLOW if "忙碌" in status['status'] else Colors.RED
            print(f"{status['name']:<12} {status['role']:<12} {status['load']:<10} "
                  f"{status['success_rate']:<8} {color}{status['status']}{Colors.NC}")
        
        # 任务队列
        tasks = self.router.get_task_queue()
        if tasks:
            print(f"\n{Colors.BOLD}任务队列 ({len(tasks)}):{Colors.NC}")
            for task in tasks[:10]:
                priority_color = Colors.RED if task['priority'] == 'CRITICAL' else \
                                Colors.YELLOW if task['priority'] == 'HIGH' else Colors.NC
                print(f"  [{priority_color}{task['priority']}{Colors.NC}] "
                      f"{task['type']:<12} {task['status']:<10} {task['content']}")
        
        # 消息总线状态
        print(f"\n{Colors.BOLD}消息总线:{Colors.NC}")
        for agent_id in self.router.agents:
            pending = self.bus.get_pending_count(agent_id)
            if pending > 0:
                print(f"  {agent_id}: {pending} 条待处理消息")
    
    def cmd_dispatch(self, args):
        """调度任务"""
        task_content = args.task
        
        # 确定优先级
        priority = TaskPriority.NORMAL
        if args.priority:
            priority = TaskPriority[args.priority.upper()]
        
        selected_agent = args.agent
        if selected_agent and selected_agent not in self.router.agents:
            print(f"{Colors.RED}错误: Agent '{selected_agent}' 不存在{Colors.NC}")
            return

        routed_agent_id, task = self.router.route_task(task_content, priority)

        if selected_agent:
            agent_id = selected_agent
            if routed_agent_id != agent_id:
                self.router.agents[routed_agent_id].current_tasks = max(
                    0, self.router.agents[routed_agent_id].current_tasks - 1
                )
                self.router.agents[agent_id].current_tasks += 1
                task.assigned_agent = agent_id

            print(f"{Colors.YELLOW}调度到指定Agent: {self.router.agents[agent_id].name}{Colors.NC}")
        else:
            agent_id = routed_agent_id
            agent = self.router.agents[agent_id]
            print(f"{Colors.GREEN}智能路由结果:{Colors.NC}")
            print(f"  任务类型: {task.type.value}")
            print(f"  分配给: {agent.name} ({agent.role})")
            print(f"  匹配分数: 技能匹配 + 负载均衡 + 历史表现")
        
        # 发送任务消息
        msg = self.bus.create_task_message(
            "pm", agent_id, task.id, task_content,
            MessagePriority[priority.name]
        )
        self.bus.send(msg)
        
        print(f"\n{Colors.GREEN}✓ 任务已发送{Colors.NC}")
        print(f"  任务: {task_content}")
        
        # 记录指标
        self.monitor.record_agent_metric(agent_id, "tasks_assigned", 1)
    
    def cmd_broadcast(self, args):
        """广播消息"""
        from core.message_bus import Message
        
        msg = Message.create(
            MessageType.BROADCAST,
            "pm",
            None,
            {"message": args.message},
            MessagePriority.HIGH if args.urgent else MessagePriority.NORMAL
        )
        
        self.bus.send(msg)
        print(f"{Colors.GREEN}✓ 广播消息已发送: {args.message}{Colors.NC}")
    
    def cmd_workflow(self, args):
        """执行工作流"""
        from core.workflow_engine import WorkflowEngine, create_standard_project_workflow
        
        engine = WorkflowEngine(self.router, self.bus)
        
        if args.list:
            print(f"{Colors.BOLD}可用工作流:{Colors.NC}")
            print("  1. standard-project - 标准项目开发流程")
            print("  2. quick-start - 快速启动流程")
            return
        
        # 创建并执行标准工作流
        steps = create_standard_project_workflow()
        workflow = engine.create_workflow(
            f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            args.name or "项目开发",
            "自动执行的项目开发工作流",
            steps,
            {"project_name": args.name or "新项目"}
        )
        
        print(f"{Colors.GREEN}启动工作流: {workflow.name}{Colors.NC}")
        print(f"步骤数: {len(workflow.steps)}")
        print(f"\n执行中...")
        
        # 执行工作流
        result = engine.execute_workflow(workflow.id)
        
        if result['success']:
            print(f"\n{Colors.GREEN}✓ 工作流执行完成{Colors.NC}")
            print(f"  耗时: {result.get('duration', 0):.1f}秒")
            print(f"  完成步骤: {', '.join(result['completed_steps'])}")
        else:
            print(f"\n{Colors.RED}✗ 工作流执行失败{Colors.NC}")
            print(f"  错误: {result.get('error', '未知错误')}")
    
    def cmd_monitor(self, args):
        """监控命令"""
        if args.dashboard:
            # 显示仪表盘
            dashboard = self.monitor.get_dashboard_data()
            
            print(f"\n{Colors.BOLD}=== 监控仪表盘 ==={Colors.NC}\n")
            
            # 摘要
            summary = dashboard['summary']
            print(f"{Colors.BOLD}摘要:{Colors.NC}")
            print(f"  总告警: {summary['total_alerts']}")
            print(f"  未解决: {summary['unresolved_alerts']}")
            print(f"  严重: {summary['critical_alerts']}")
            
            # Agent负载
            if dashboard['agent_loads']:
                print(f"\n{Colors.BOLD}Agent负载:{Colors.NC}")
                for agent_id, load in dashboard['agent_loads'].items():
                    color = Colors.GREEN if load < 0.5 else Colors.YELLOW if load < 0.8 else Colors.RED
                    bar = "█" * int(load * 20) + "░" * (20 - int(load * 20))
                    print(f"  {agent_id:<15} {color}{bar}{Colors.NC} {load:.1%}")
            
            # 最近告警
            if dashboard['recent_alerts']:
                print(f"\n{Colors.BOLD}最近告警:{Colors.NC}")
                for alert in dashboard['recent_alerts']:
                    color = Colors.RED if alert['level'] == 'critical' else Colors.YELLOW
                    print(f"  {color}[{alert['level']}] {alert['message']}{Colors.NC}")
        
        elif args.logs:
            # 显示日志
            logs = self.monitor.get_logs(limit=args.limit or 20)
            print(f"\n{Colors.BOLD}=== 最近日志 ==={Colors.NC}\n")
            for log in logs:
                color = Colors.RED if log['level'] == 'ERROR' else \
                        Colors.YELLOW if log['level'] == 'WARNING' else Colors.NC
                print(f"[{log['datetime']}] {color}[{log['level']}] {Colors.NC}{log['message']}")
        
        elif args.export:
            # 导出指标
            filepath = args.export
            self.monitor.export_metrics(filepath)
            print(f"{Colors.GREEN}✓ 指标已导出到: {filepath}{Colors.NC}")
    
    def cmd_interactive(self, args):
        """交互式模式"""
        self.print_banner()
        
        commands = {
            'status': '查看团队状态',
            'dispatch': '调度任务',
            'broadcast': '广播消息',
            'workflow': '执行工作流',
            'monitor': '监控面板',
            'help': '显示帮助',
            'quit': '退出',
        }
        
        while True:
            try:
                print(f"\n{Colors.CYAN}team>{Colors.NC} ", end='')
                cmd = input().strip().lower()
                
                if cmd == 'quit' or cmd == 'exit':
                    print(f"{Colors.GREEN}再见!{Colors.NC}")
                    break
                elif cmd == 'help':
                    print(f"\n{Colors.BOLD}可用命令:{Colors.NC}")
                    for cmd_name, desc in commands.items():
                        print(f"  {cmd_name:<12} - {desc}")
                elif cmd == 'status':
                    self.cmd_status(argparse.Namespace())
                elif cmd.startswith('dispatch '):
                    task = cmd[9:]
                    self.cmd_dispatch(argparse.Namespace(agent=None, task=task, priority=None))
                elif cmd == 'monitor':
                    self.cmd_monitor(argparse.Namespace(dashboard=True, logs=False, export=None, limit=20))
                else:
                    print(f"{Colors.YELLOW}未知命令，输入 'help' 查看帮助{Colors.NC}")
                    
            except KeyboardInterrupt:
                print(f"\n{Colors.GREEN}再见!{Colors.NC}")
                break
            except Exception as e:
                print(f"{Colors.RED}错误: {e}{Colors.NC}")


def main():
    parser = argparse.ArgumentParser(
        description='AI Agent 团队调度框架 CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s status                    # 查看团队状态
  %(prog)s dispatch "开发登录接口"    # 智能调度任务
  %(prog)s dispatch -a backend-1 "任务"  # 指定Agent
  %(prog)s broadcast "项目启动"       # 广播消息
  %(prog)s workflow -n "电商平台"     # 执行工作流
  %(prog)s monitor --dashboard       # 监控仪表盘
  %(prog)s interactive               # 交互式模式
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看团队状态')
    
    # dispatch 命令
    dispatch_parser = subparsers.add_parser('dispatch', help='调度任务')
    dispatch_parser.add_argument('task', help='任务描述')
    dispatch_parser.add_argument('-a', '--agent', help='指定Agent')
    dispatch_parser.add_argument('-p', '--priority', choices=['critical', 'high', 'normal', 'low'],
                                help='任务优先级')
    
    # broadcast 命令
    broadcast_parser = subparsers.add_parser('broadcast', help='广播消息')
    broadcast_parser.add_argument('message', help='消息内容')
    broadcast_parser.add_argument('-u', '--urgent', action='store_true', help='紧急消息')
    
    # workflow 命令
    workflow_parser = subparsers.add_parser('workflow', help='执行工作流')
    workflow_parser.add_argument('-n', '--name', help='项目名称')
    workflow_parser.add_argument('-l', '--list', action='store_true', help='列出工作流')
    
    # monitor 命令
    monitor_parser = subparsers.add_parser('monitor', help='监控面板')
    monitor_parser.add_argument('-d', '--dashboard', action='store_true', help='显示仪表盘')
    monitor_parser.add_argument('-l', '--logs', action='store_true', help='查看日志')
    monitor_parser.add_argument('-e', '--export', help='导出指标到文件')
    monitor_parser.add_argument('--limit', type=int, help='日志条数限制')
    
    # interactive 命令
    interactive_parser = subparsers.add_parser('interactive', help='交互式模式')
    
    args = parser.parse_args()
    
    cli = TeamCLI()
    
    if args.command == 'status':
        cli.cmd_status(args)
    elif args.command == 'dispatch':
        cli.cmd_dispatch(args)
    elif args.command == 'broadcast':
        cli.cmd_broadcast(args)
    elif args.command == 'workflow':
        cli.cmd_workflow(args)
    elif args.command == 'monitor':
        cli.cmd_monitor(args)
    elif args.command == 'interactive':
        cli.cmd_interactive(args)
    else:
        cli.print_banner()
        parser.print_help()


if __name__ == '__main__':
    main()
