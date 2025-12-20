# 0) (one-time) Create an ECR repo
aws ecr create-repository --repository-name my-vision-lambda

# 1) Authenticate Docker to ECR
aws ecr get-login-password --region ap-south-1 \
| docker login --username AWS --password-stdin 963311703323.dkr.ecr.ap-south-1.amazonaws.com

# 2) Build (add --platform if building x86 on Apple Silicon)
docker build --no-cache -t my-vision-lambda .

# 3) Tag and push
docker tag my-vision-lambda:latest 963311703323.dkr.ecr.ap-south-1.amazonaws.com/my-vision-lambda:latest
docker push 963311703323.dkr.ecr.ap-south-1.amazonaws.com/my-vision-lambda:latest

# 4) Create/Update Lambda to use this image
# aws lambda update-function-code \
#   --function-name my-vision-lambda \
#   --package-type Image \
#   --code ImageUri=963311703323.dkr.ecr.ap-south-1.amazonaws.com/my-vision-lambda:latest \
#   --role arn:aws:iam::963311703323:role/LambdaBasicExecutionRole

# ...or update-function-code for an existing function
# aws lambda update-function-code \
#     --function-name my-vision-lambda \
#     --image-uri 963311703323.dkr.ecr.ap-south-1.amazonaws.com/my-vision-lambda:latest



aws lambda create-function \
  --function-name my-vision-lambda \
  --package-type Image \
  --code ImageUri=963311703323.dkr.ecr.ap-south-1.amazonaws.com/my-vision-lambda:latest \
  --role arn:aws:iam::963311703323:role/LambdaBasicExecutionRole
