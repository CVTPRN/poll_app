provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "app_server" {
  ami           = "ami-0c55b159cbfafe1f0"  # Use a relevant AMI
  instance_type = "t2.micro"

  vpc_security_group_ids = [aws_security_group.app_sg.id]

  key_name = "your-key-pair"

  user_data = file("userdata.sh")  # EC2 initialization script

  associate_public_ip_address = true

  tags = {
    Name = "AppServer"
  }
}

resource "aws_s3_bucket" "static_files" {
  bucket = "my-app-static-files"
  acl    = "public-read"
}

resource "aws_lambda_function" "voting_lambda" {
  filename         = "lambda_function.zip"
  function_name    = "VotingFunction"
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.8"
  role             = aws_iam_role.lambda_exec.arn
}
