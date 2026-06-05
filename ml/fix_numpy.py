import glob, json, os

for fpath in glob.glob(r'd:\hackathob\pharmasense\ml\notebooks\*.ipynb'):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        if not content: continue
        nb = json.loads(content)
    
    modified = False
    for cell in nb.get('cells', []):
        if cell.get('cell_type') == 'code':
            source = cell.get('source', [])
            new_source = []
            for line in source:
                if "'numpy'" in line:
                    new_source.append(line.replace("'numpy'", "'numpy<2.0.0'"))
                    modified = True
                else:
                    new_source.append(line)
            cell['source'] = new_source
            
    if modified:
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=1)
        print(f"Pinned numpy<2.0.0 in {os.path.basename(fpath)}")
