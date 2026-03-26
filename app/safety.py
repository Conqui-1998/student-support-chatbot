Sensitive_Keywords = [
"suicide", "self-harm", "depressed", "panic attack", "anxiety", "mental health", "crisis", "unsafe", "harm"
]

Category_Keywords = {
"wellbeing": ["wellbeing", "mental health", "counselling", "support", "anxiety"],
"assessments": ["assessment", "deadline", "extension", "submission", "exam"],
"admissions": ["admissions", "apply", "application", "offer", "entry requirements"],
"general": ["contact", "help", "student services", "general"]
}

def is_sensitive_query(text: str) -> bool:
    text = text.lower()
    return any(keyword in text for keyword in Sensitive_Keywords)
    
def classify_query(text: str) -> str:
    text = text.lower()
    for category, keywords in Category_Keywords.items():
        if any(k in text for k in keywords):
            return category
    return "general"