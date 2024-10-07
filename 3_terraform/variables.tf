variable "region" {
  description = "The AWS region to deploy the resources in"
  default     = "us-east-1"
}

variable "instance_type" {
  description = "The type of EC2 instance to launch"
  default     = "t2.micro"
}
