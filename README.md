# Marathon Project

This repository contains the code for the Marathon project, including Lambda functions for video processing.

## Lambda Deployment

To deploy the Lambda function, follow these steps:

1.  **Important:** Upload your `sa.json` (Service Account credentials) file to the `lambda` directory. This file is required for the function to operate but is excluded from git.

2.  Navigate to the lambda directory:
    ```bash
    cd lambda
    ```

3.  Run the deployment script:
    ```bash
    ./deploy.sh
    ```
