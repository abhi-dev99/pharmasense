import json

filepath = 'd:/hackathob/pharmasense/ml/notebooks/02_train_tft.ipynb'
with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        if 'MAX_EPOCHS         = 15' in source:
            source = source.replace('MAX_EPOCHS         = 15', 'MAX_EPOCHS         = 8')
            source = source.replace("DRIVE_OUTPUT = '/content/pharmasense_models/'", "DRIVE_OUTPUT = '/content/drive/MyDrive/pharmasense_models/'")
            lines = [line + '\n' for line in source.split('\n')]
            if lines and lines[-1] == '\n': lines.pop()
            elif lines and lines[-1].endswith('\n'): lines[-1] = lines[-1][:-1]
            cell['source'] = lines
            
        if '# from google.colab import drive' in source:
            source = source.replace('# from google.colab import drive', 'from google.colab import drive')
            source = source.replace("# drive.mount('/content/drive')", "drive.mount('/content/drive')")
            lines = [line + '\n' for line in source.split('\n')]
            if lines and lines[-1] == '\n': lines.pop()
            elif lines and lines[-1].endswith('\n'): lines[-1] = lines[-1][:-1]
            cell['source'] = lines

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
    
print("Successfully updated 02_train_tft.ipynb")
