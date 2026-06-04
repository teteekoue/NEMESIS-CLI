from tools import ActionExecutor
import json

def run_debug_action(executor, action_type, content):
    print(f"--- Exécution de {action_type} ---")
    try:
        for update in executor.execute_action(action_type, content):
            print(f"Feedback: {update.get('stdout')}")
    except Exception as e:
        print(f"Exception capturée: {e}")

if __name__ == "__main__":
    # Il faut charger la config pour passer la clé API à l'executor
    import yaml
    from pathlib import Path
    
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    steel_key = config.get("steel", {}).get("api_key")
    executor = ActionExecutor(steel_api_key=steel_key)
    
    # 1. Ouvrir Gemini (site complexe dynamique)
    run_debug_action(executor, "web_open", "https://gemini.google.com/app")
