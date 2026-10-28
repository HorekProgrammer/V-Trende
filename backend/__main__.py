import uvicorn


if __name__ == "__main__":
    # Стабильный процесс для автозапуска. Для разработки с hot reload:
    # python -m uvicorn backend.app:app --reload
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000)
