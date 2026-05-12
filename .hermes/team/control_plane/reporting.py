def render_bullet_section(title: str, items):
    lines = [f"## {title}"]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) + "\n"
