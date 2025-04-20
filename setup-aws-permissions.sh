#!/bin/bash

# Script to set up AWS IAM permissions for Lightsail container services
# This script requires the AWS CLI to be installed and configured

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to print error messages
print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

# Function to print information messages
print_info() {
    echo -e "$1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Get current user
print_info "Getting current AWS user..."
USER_INFO=$(aws sts get-caller-identity 2>/dev/null)

if [ $? -ne 0 ]; then
    print_error "Failed to get AWS user information. Make sure your AWS CLI is configured correctly."
    print_info "Run 'aws configure' to set up your AWS credentials."
    exit 1
fi

USER_ARN=$(echo "$USER_INFO" | grep "Arn" | cut -d'"' -f4)
USER_NAME=$(echo "$USER_ARN" | cut -d'/' -f2)

print_info "Current AWS user: $USER_NAME"
print_info "ARN: $USER_ARN"

# Create a policy document for Lightsail container services
print_info "Creating policy document for Lightsail container services..."
cat > lightsail-container-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lightsail:GetContainerServices",
                "lightsail:CreateContainerService",
                "lightsail:DeleteContainerService",
                "lightsail:UpdateContainerService",
                "lightsail:GetContainerImages",
                "lightsail:PushContainerImage",
                "lightsail:CreateContainerServiceDeployment",
                "lightsail:GetContainerServiceDeployments",
                "lightsail:GetContainerLog",
                "lightsail:GetContainerServiceMetricData"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Create the policy
print_info "Creating IAM policy 'LightsailContainerServicesPolicy'..."
POLICY_ARN=$(aws iam create-policy \
    --policy-name LightsailContainerServicesPolicy \
    --policy-document file://lightsail-container-policy.json \
    --description "Policy for Lightsail container services" \
    --query 'Policy.Arn' \
    --output text 2>/dev/null)

if [ $? -ne 0 ]; then
    print_warning "Failed to create policy. It might already exist or you don't have permissions."
    print_info "Trying to get the ARN of an existing policy..."
    
    POLICY_ARN=$(aws iam list-policies \
        --query "Policies[?PolicyName=='LightsailContainerServicesPolicy'].Arn" \
        --output text 2>/dev/null)
    
    if [ -z "$POLICY_ARN" ]; then
        print_error "Could not create or find the policy. You may need to manually attach the AmazonLightsailFullAccess policy."
        print_info "Go to AWS IAM Console: https://console.aws.amazon.com/iam/"
        print_info "Click on 'Users' and select your user"
        print_info "Click 'Add permissions' and then 'Attach policies directly'"
        print_info "Search for 'AmazonLightsailFullAccess' and attach it"
        
        # Clean up
        rm -f lightsail-container-policy.json
        exit 1
    fi
fi

print_info "Policy ARN: $POLICY_ARN"

# Attach the policy to the user
print_info "Attaching policy to user $USER_NAME..."
if ! aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn "$POLICY_ARN"; then
    
    print_error "Failed to attach policy to user. You may need to do this manually."
    print_info "Go to AWS IAM Console: https://console.aws.amazon.com/iam/"
    print_info "Click on 'Users' and select your user"
    print_info "Click 'Add permissions' and then 'Attach policies directly'"
    print_info "Search for 'LightsailContainerServicesPolicy' and attach it"
    
    # Clean up
    rm -f lightsail-container-policy.json
    exit 1
fi

print_success "Successfully attached Lightsail container services policy to user $USER_NAME"
print_info "You should now have the necessary permissions to deploy to AWS Lightsail container services."
print_info "Try running ./deploy-lightsail.sh again."

# Clean up
rm -f lightsail-container-policy.json

print_info "Note: IAM permission changes may take a few minutes to propagate."
