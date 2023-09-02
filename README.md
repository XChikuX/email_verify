# Email Verifier 
This is a FastAPI project that includes email verification features.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.6+
- FastAPI
- Hypercorn

### Installation

1. **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/yourrepository.git
    ```

2. **Navigate to the project directory:**
    ```bash
    cd yourrepository
    ```

3. **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Server

To run the server, execute the following command:

```bash
hypercorn --bind 0.0.0.0:1234 verify:app
