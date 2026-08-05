import os
import re
import sys

def fix_template_file(filepath):
    """Fix cramped Django template tags by adding proper line breaks."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Fix 1: {% extends %} followed immediately by {% block %} on same line
    content = re.sub(
        r'\{%\s*extends\s+[\'"][^\'"]+[\'"]\s*\%}\s*\{%\s*block',
        lambda m: m.group(0).replace('{% block', '\n\n{% block', 1),
        content
    )

    # Fix 2: {% block title %}...{% endblock %} on same line -> separate lines
    content = re.sub(
        r'(\{%\s*block\s+\w+\s*\%})(.+?)(\{%\s*endblock\s*\%})',
        r'\1\2\3',
        content
    )

    # Fix 3: Split any line that has multiple {% %} tags crammed together
    # This is the nuclear option - split EVERY {% %} tag onto its own line
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        # Check if line has multiple {% ... %} tags
        tags = re.findall(r'\{%\s*[^%]+\s*\%}', line)
        if len(tags) > 1 and not line.strip().startswith('<!--'):
            # Split each tag onto its own line
            parts = re.split(r'(\{%\s*[^%]+\s*\%})', line)
            for part in parts:
                part = part.strip()
                if part:
                    new_lines.append(part)
        else:
            new_lines.append(line)

    content = '\n'.join(new_lines)

    # Fix 4: Ensure {% extends %} is alone on its line with blank lines after
    content = re.sub(
        r'^(\{%\s*extends\s+[\'"][^\'"]+[\'"]\s*\%})\s*\n?',
        r'\1\n\n',
        content,
        flags=re.MULTILINE
    )

    # Fix 5: Ensure {% block X %} and {% endblock %} have proper spacing
    content = re.sub(
        r'(\{%\s*endblock\s*\%})\s*(\{%\s*block)',
        r'\1\n\n\2',
        content
    )

    # Fix 6: Ensure {% block X %}...{% endblock %} where ... is text
    # Put tag and text on separate lines if they're mashed together
    content = re.sub(
        r'(\{%\s*block\s+\w+\s*\%})([^\n])(?!\n)',
        r'\1\n\2',
        content
    )

    # Fix 7: Put {% endblock %} on its own line if preceded by non-whitespace
    content = re.sub(
        r'([^\n\s])(\{%\s*endblock)',
        r'\1\n\2',
        content
    )

    # Fix 8: Clean up excessive blank lines (max 2)
    content = re.sub(r'\n{4,}', '\n\n\n', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        print(f"  FIXED: {filepath}")
        return True
    else:
        print(f"  OK:    {filepath}")
        return False


def scan_and_fix(directory):
    """Scan all HTML files and fix them."""
    fixed_count = 0
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.html'):
                filepath = os.path.join(root, filename)
                if fix_template_file(filepath):
                    fixed_count += 1
    return fixed_count


if __name__ == '__main__':
    templates_dir = os.path.join('.', 'templates')

    if not os.path.exists(templates_dir):
        print(f"ERROR: 'templates' folder not found in current directory.")
        print(f"Current directory: {os.path.abspath('.')}")
        print("Run this script from your project root (where manage.py is).")
        sys.exit(1)

    print("Scanning templates folder...")
    print("-" * 50)
    fixed = scan_and_fix(templates_dir)
    print("-" * 50)

    if fixed > 0:
        print(f"\nFixed {fixed} file(s). Restart your server and refresh the page.")
    else:
        print("\nAll files look clean. If you're still getting errors,")
        print("the issue might be in your base.html or the error is from a cached file.")
        print("Try: python manage.py collectstatic --clear")
