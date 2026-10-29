# Good First Issue Agent 🔍

An AI-powered GitHub repository assistant that helps developers discover and understand potential beginner-friendly issues using Gemma 4.

## 🎯 Problem

Beginners often struggle to choose an open-source repository and find a suitable issue to work on. Understanding a project's structure and deciding where to start can be challenging.

## 💡 Solution

Good First Issue Agent analyzes a GitHub repository and helps users explore open issues. It uses an AI model to analyze repository information and issue details, then checks recommendations against GitHub's actual issue data.

## ✨ Features

- Accepts a GitHub repository URL.
- Retrieves repository information and open issues.
- Uses Gemma 4 for AI-powered analysis.
- Verifies recommended issue links against GitHub's API.
- Checks whether recommended issues are still open.
- Searches Python source code for relevant terms.
- Provides a local fallback when AI tool calling is unsuccessful.
- Includes a Streamlit interface.

## 🛠️ Technology Stack

- Python
- Google Gen AI SDK
- Gemma 4
- GitHub REST API
- Streamlit
- Requests
- python-dotenv

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/anuragtiwari73219-byte/good-first-issue-agent.git
cd good-first-issue-agent
````

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root and configure the API key required by the Google Gen AI SDK.

Never commit API keys or other secrets to GitHub.

### 5. Run the application

```bash
streamlit run app.py
```

Open the local address displayed in the terminal.

## 🔄 How It Works

1. The user enters a GitHub repository URL.
2. The application parses the repository owner and name.
3. It retrieves repository information and open issues from GitHub.
4. Gemma 4 analyzes the available information and generates recommendations.
5. The application checks recommended issue references against GitHub's live API.
6. The user reviews the results and decides which issue to investigate further.

## 🔐 Responsible Use

* Recommendations are suggestions, not guarantees that an issue is suitable for every beginner.
* GitHub issue status can change after verification.
* Users should review the repository's contribution guidelines before submitting a pull request.
* The application does not automatically create or submit pull requests.

## 🚧 Current Scope

This project focuses on repository inspection, issue discovery, AI-assisted analysis, and recommendation verification. Results depend on the repository's available data, API access, and model responses.

## 👨‍💻 Author

Anurag Tiwari

* GitHub: https://github.com/anuragtiwari73219-byte
* LinkedIn: https://linkedin.com/in/anurag-tiwari-42079a356

---

Built as an open-source contribution assistant project.
