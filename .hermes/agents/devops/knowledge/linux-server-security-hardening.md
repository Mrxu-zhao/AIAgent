# Linux 服务器安全加固指南

## 概述

本文档介绍 Linux 服务器的安全加固措施，包括 SSH 安全配置、防火墙设置、用户权限管理等。

## 1. SSH 安全加固

### 1.1 SSH 配置文件

```bash
# /etc/ssh/sshd_config
PermitRootLogin no                    # 禁止 root 登录
PubkeyAuthentication yes              # 启用公钥认证
PasswordAuthentication no             # 禁用密码认证
MaxAuthTries 3                       # 最大认证尝试次数
ClientAliveInterval 300              # 客户端存活检测
X11Forwarding no                      # 禁用 X11 转发
Port 22022                            # 更改默认端口
```

### 1.2 生成 SSH 密钥

```bash
# 生成 ED25519 密钥（推荐）
ssh-keygen -t ed25519 -C "your-email@example.com"

# 复制公钥到服务器
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server-ip
```

### 1.3 Fail2ban 防暴力破解

```bash
# 安装
yum install -y fail2ban

# 配置
cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = 22022
logpath = /var/log/secure
maxretry = 3
EOF

systemctl enable fail2ban
systemctl start fail2ban
```

## 2. 防火墙配置

### 2.1 firewalld 配置

```bash
# 启动 firewalld
systemctl start firewalld
systemctl enable firewalld

# 放通常用端口
firewall-cmd --permanent --add-port=22/tcp    # SSH
firewall-cmd --permanent --add-port=80/tcp    # HTTP
firewall-cmd --permanent --add-port=443/tcp   # HTTPS
firewall-cmd --permanent --add-port=8080/tcp  # Spring Boot

# 重新加载
firewall-cmd --reload

# 查看规则
firewall-cmd --list-all
```

### 2.2 iptables 基础规则

```bash
# 查看现有规则
iptables -L -n -v

# 保存规则
service iptables save
```

## 3. 用户权限管理

### 3.1 用户管理

```bash
# 创建用户
useradd -m -s /bin/bash deploy
usermod -aG wheel deploy          # 添加到 sudo 组

# 设置密码
passwd deploy

# 锁定用户
usermod -L username
```

### 3.2 sudo 权限配置

```bash
# 编辑 sudoers（使用 visudo）
visudo

# 示例：允许 deploy 用户无密码执行 docker
deploy ALL=(ALL) NOPASSWD: /usr/bin/docker
```

### 3.3 文件权限

```bash
# SSH 密钥权限
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# 应用目录权限
chown -R deploy:deploy /opt/app
chmod -R 755 /opt/app
```

## 4. 系统安全加固

### 4.1 SELinux 配置

```bash
# 查看状态
getenforce

# 临时关闭
setenforce 0

# 永久关闭
sed -i 's/SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config
```

### 4.2 禁用不必要服务

```bash
# 查看运行中的服务
systemctl list-units --type=service --state=running

# 禁用不需要的服务
systemctl stop postfix cups avahi-daemon
systemctl disable postfix cups avahi-daemon
```

### 4.3 系统参数加固

```bash
# /etc/sysctl.conf
net.ipv4.tcp_syncookies = 1
net.ipv4.icmp_echo_ignore_all = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0

# 生效
sysctl -p
```

## 5. 日志审计

### 5.1 SSH 登录审计

```bash
# 查看登录记录
last
lastlog

# 查看失败的登录
lastb
cat /var/log/secure | grep "Failed password"

# 实时监控
tail -f /var/log/secure
```

### 5.2 auditd 审计

```bash
# 安装
yum install -y audit

# 启动
systemctl enable auditd
systemctl start auditd

# 配置审计规则
cat > /etc/audit/rules.d/audit.rules <<EOF
-w /etc/passwd -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/ssh/sshd_config -p wa -k sshd_config
EOF

auditctl -R /etc/audit/rules.d/audit.rules
```

## 6. 安全检查清单

### 6.1 部署前检查

- [ ] 修改默认 SSH 端口
- [ ] 禁用 root 登录
- [ ] 配置 SSH 公钥认证
- [ ] 安装配置 Fail2ban
- [ ] 配置防火墙规则
- [ ] 禁用不必要的服务
- [ ] 配置系统参数
- [ ] 设置资源限制

### 6.2 定期巡检

```bash
#!/bin/bash
# security_check.sh - 安全巡检脚本

echo "========== 安全巡检报告 =========="

# SSH 暴力破解尝试
echo "【SSH 暴力破解尝试 Top 10】"
lastb | awk '{print $3}' | sort | uniq -c | sort -rn | head -10

# 新用户
echo ""
echo "【最近创建的用户】"
cut -d: -f1,3,4 /etc/passwd | awk -F: '$2>=1000 {print}'

# 开放端口
echo ""
echo "【监听端口】"
netstat -tlnp | grep -v "127.0.0.1"
```
