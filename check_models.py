import google.generativeai as genai
genai.configure(api_key="AIzaSyA1TguSP6YXRIPqxZFqFF46QgZs7L1lj7s")

print("Available models:")
for m in genai.list_models():
    print(" •", m.name)
