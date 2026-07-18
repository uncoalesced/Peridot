import os
import tokenize
import io
import re

# Files to process
TARGET_FILES = [
    'server.py',
    'ui.py',
    'core.py',
    'launcher.py'
]

# Add all files in core_system
for root, dirs, files in os.walk('core_system'):
    for file in files:
        if file.endswith('.py'):
            TARGET_FILES.append(os.path.join(root, file))

def should_keep(comment_text, line_index):
    # Top-of-file headers (roughly first 30 lines)
    if line_index < 30 and any(kw in comment_text for kw in ['Copyright', 'License', 'v1.5.3', 'Engineered', 'uncoalesced']):
        return True
    
    # Structural ASCII headers
    if '---' in comment_text or '===' in comment_text or '___' in comment_text:
        return True
    
    # Critical Algorithmic Logic
    keep_keywords = [
        'RRF', 'scoring loop', '200MB', 'watchdog', 'safety bound', 
        'WebSocket', 'SIGSTOP', 'mathematical', 'hardware timing',
        'parent-child', 'hierarchical chunking', 'Reciprocal Rank Fusion', 
        'FlashRank', 'cross-encoder', 'Flash attention', 'latency bounds'
    ]
    
    if any(re.search(re.escape(kw), comment_text, re.IGNORECASE) for kw in keep_keywords):
        return True
        
    return False

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    
    lines = source.split('\n')
    lines_to_modify = {} # line_no (1-based) -> new line text
    
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            comment_text = tok.string
            start_row, start_col = tok.start
            
            if not should_keep(comment_text, start_row):
                orig_line = lines[start_row - 1]
                new_line = orig_line[:start_col].rstrip()
                lines_to_modify[start_row] = new_line
                
    new_lines = []
    for i, line in enumerate(lines, 1):
        if i in lines_to_modify:
            new_line = lines_to_modify[i]
            if new_line == "" and line.strip().startswith('#'):
                continue
            new_lines.append(new_line)
        else:
            new_lines.append(line)
            
    new_source = '\n'.join(new_lines)
    
    # Clean up multiple consecutive blank lines
    new_source = re.sub(r'\n{3,}', '\n\n', new_source)
    
    orig_lines = len(lines)
    new_line_count = len(new_source.split('\n'))
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_source)
        
    return orig_lines, new_line_count

def main():
    total_orig = 0
    total_new = 0
    results = []
    
    for fpath in TARGET_FILES:
        if os.path.exists(fpath):
            try:
                orig, new = clean_file(fpath)
                total_orig += orig
                total_new += new
                results.append((fpath, orig, new))
            except Exception as e:
                print(f"Error processing {fpath}: {e}")
                
    with open('cleanup_report.txt', 'w', encoding='utf-8') as f:
        f.write("File | Original Lines | New Lines | Reduction\n")
        f.write("--- | --- | --- | ---\n")
        for fpath, orig, new in results:
            reduction = orig - new
            f.write(f"{fpath} | {orig} | {new} | -{reduction}\n")
            
    print(f"Total original lines: {total_orig}")
    print(f"Total new lines: {total_new}")
    print(f"Total reduction: {total_orig - total_new}")
    print("Cleanup complete.")

if __name__ == '__main__':
    main()
