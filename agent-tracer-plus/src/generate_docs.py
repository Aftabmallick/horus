import ast
import os
import shutil

SRC_DIR = "agent_tracer_plus"
DOCS_DIR = "../../docs-site/docs/agent-tracer-plus/api"

def sanitize(text):
    if not text:
        return ""
    # Escape < > { } to prevent MDX parser errors
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("{", "&#123;").replace("}", "&#125;")

def generate_markdown_for_file(filepath, relative_path):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return
        
    module_doc = sanitize(ast.get_docstring(tree))
    
    # Safely get module name without .py extension
    module_name = os.path.splitext(relative_path)[0].replace(os.sep, '.')
    if module_name.endswith('.__init__'):
        module_name = module_name[:-9]
        
    md_content = f"# Module: `{module_name}`\n\n"
    if module_doc:
        md_content += f"{module_doc}\n\n"
        
    has_content = bool(module_doc)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            has_content = True
            md_content += f"## Class `{node.name}`\n"
            doc = sanitize(ast.get_docstring(node))
            if doc:
                md_content += f"{doc}\n\n"
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    func_doc = sanitize(ast.get_docstring(item))
                    args = [a.arg for a in item.args.args]
                    md_content += f"### `def {item.name}({', '.join(args)})`\n"
                    if func_doc:
                        md_content += f"{func_doc}\n\n"
                        
        elif isinstance(node, ast.FunctionDef):
            has_content = True
            doc = sanitize(ast.get_docstring(node))
            args = [a.arg for a in node.args.args]
            md_content += f"## Function `{node.name}({', '.join(args)})`\n"
            if doc:
                md_content += f"{doc}\n\n"

    if has_content:
        out_path = os.path.join(DOCS_DIR, f"{module_name}.md")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

def main():
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
    os.makedirs(DOCS_DIR)
        
    for root, _, files in os.walk(SRC_DIR):
        for file in files:
            if file.endswith('.py') and file != "_version.py":
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, ".")
                generate_markdown_for_file(filepath, rel_path)
                
if __name__ == "__main__":
    main()
