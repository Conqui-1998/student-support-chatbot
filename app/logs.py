from typing import List, Dict, Any

chat_logs: List[Dict[str, Any]] = []

Max_logs = 20

def add_log(entry: Dict[str, Any]) -> None:
    chat_logs.append(entry)
    
    if len(chat_logs) > Max_logs:
        del chat_logs[0]
        
def get_logs() -> List[Dict[str, Any]]:
    return list (reversed(chat_logs))