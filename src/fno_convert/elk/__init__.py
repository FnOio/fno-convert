import subprocess
import json
import os

def elk_layout(elk_json):
    js_dir = os.path.dirname(__file__)
    node_script = os.path.join(js_dir, "elk_layout.js")
    
    try:
        process = subprocess.Popen(
            ["node", node_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=js_dir,
        )
        
        json_input = json.dumps(elk_json)
        stdout, stderr = process.communicate(json_input)
        
        if stderr:
            raise Exception(f"JavaScript Error: {stderr}")
        
        return json.loads(stdout)
    
    except Exception as e:
        print(f"Error: {e}")
        return None