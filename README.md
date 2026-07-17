# CC-Chatbot-v2 Prototype

An AI-powered Chatbot prototype for CollarCheck, featuring resume analysis and job recommendations.

## Project Structure
- `/backend`: FastAPI Python server containing the chatbot logic, SQLite database integration, and Groq LLM configuration.
- `/frontend`: HTML/JS frontend interface.
- `/database`: Raw dataset CSV files.

---

## Getting Started

### 1. Backend Setup

#### Prerequisites
- Python 3.10 or higher installed.

#### Installation
1. Open your terminal and navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - **Windows (Command Prompt)**:
     ```cmd
     venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```
4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

#### Configuration
1. In the root directory of the project, create a `.env` file (you can copy `.env.example` as a starting point):
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and configure your Groq API Key:
   ```env
   GROQ_API_KEY=your_actual_groq_api_key
   ```

#### Running the Backend
Run the FastAPI development server:
```bash
python -m uvicorn main:app --port 8001 --reload
```
The backend API will be running at `http://localhost:8001`.

---

### 2. Frontend Setup

1. Open `frontend/index.html` directly in a web browser, or serve it using a lightweight HTTP server (e.g. VS Code Live Server or python's `http.server`).
2. By default, the frontend connects to `http://localhost:8001`. 
3. If your backend is running on a different port or host, click the **⚙️ (Settings)** icon in the top right corner of the chat window to change the **Backend URL**.
