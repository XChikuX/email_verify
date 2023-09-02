# Email Verifier 
This is a FastAPI project that includes email verification features.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.9+
- FastAPI
- Hypercorn
- Other dependencies... (see pyproject.toml)

### Installation

1. **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/yourrepository.git
    ```

2. **Create a python virtual environment:**
    ```bash
    python3 -m venv .env
    source .env/bin/activate
    ```

3. **Install the required packages:**
    ```bash
    pip install poetry
    poetry install
    ```

### Running the Server

To run the server, execute the following command:

```bash
hypercorn --bind 0.0.0.0:1234 verify:app
