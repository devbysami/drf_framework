# DRF Framework

This repository provides a Django REST Framework (DRF) solution for token generation, validation, and permission management. It includes functionality for generating secure tokens for user authentication and ensuring tokens are valid and not expired through custom permissions.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Code Structure](#code-structure)
- [License](#license)

## Features

- **Token Generation**: Automatically generates a secure token when the user provides valid credentials.
- **Token Validation**: Ensures that tokens are valid and not expired before granting access to views.
- **Custom Permissions**: Implements a custom permission class to verify the token provided in the Authorization header.
- **Error Handling**: Provides detailed error responses for invalid tokens or expired tokens.

## Installation

To install and run this project, follow these steps:

1. Clone the repository:

   ```bash
   git clone https://github.com/devbysami/drf_framework.git
   cd drf_framewor
    ```

2. Create and activate a virtual environment (optional but recommended):

  ```bash
  python -m venv venv
  source venv/bin/activate
  ```

3. Install the required dependencies:

  ```bash
  pip install -r requirements.txt
  ```

4. Set up your Django application:

  Ensure that you have django and djangorestframework installed.
  Apply migrations for UserToken and other models:

  ```bash
  python manage.py migrate
  ```


  
