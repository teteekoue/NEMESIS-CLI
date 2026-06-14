import json
from tools import ActionExecutor

def run_debug_action(action_type, content):
    executor = ActionExecutor()
    print(f"--- Exécution de {action_type} ---")
    try:
        for update in executor.execute_action(action_type, content):
            print(f"Feedback: {update.get('stdout')}")
    except Exception as e:
        print(f"Exception capturée: {e}")

if __name__ == "__main__":
    # Test web_search
    run_debug_action("web_search", "météo paris")
