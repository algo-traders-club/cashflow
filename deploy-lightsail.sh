#!/bin/bash

# AWS Lightsail deployment script for Cashflow Trading Agent
# This script helps deploy the Cashflow trading agent to AWS Lightsail

# Configuration
SERVICE_NAME="cashflow-trading"
REGION="us-west-2"  # Change to your preferred AWS region
BUNDLE_ID="micro_2_0"  # 2GB RAM, 1 vCPU
BLUEPRINT_ID="amazon_linux_2"
PORT="9001"

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

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install it first."
    exit 1
fi

# Check if jq is installed (needed for JSON parsing)
if ! command -v jq &> /dev/null; then
    print_error "jq is not installed. Please install it first with 'brew install jq'."
    exit 1
fi

# Build Docker image
print_info "Building Docker image..."
docker build -t cashflow-trading . || { print_error "Docker build failed"; exit 1; }

# Check AWS Lightsail permissions
print_info "Checking AWS Lightsail permissions..."
HAS_PERMISSIONS=false

# Try to list container services to check permissions
aws lightsail get-container-services --region $REGION &> /dev/null
if [ $? -eq 0 ]; then
    HAS_PERMISSIONS=true
    print_success "You have the necessary permissions to access Lightsail container services."
else
    print_warning "Limited AWS Lightsail permissions detected."
    print_info ""
    print_info "You have two options:"
    print_info ""
    print_info "Option 1: Use AWS Lightsail Console for deployment"
    print_info "1. Go to AWS Lightsail Console: https://console.aws.amazon.com/lightsail/"
    print_info "2. Click on 'Containers'"
    print_info "3. Click 'Create container service'"
    print_info "4. Select 'Micro' ($BUNDLE_ID) with 1 node"
    print_info "5. Name your service '$SERVICE_NAME'"
    print_info "6. After creation, click 'Upload container image'"
    print_info "7. Configure with port $PORT and environment variables:"
    print_info "   - CONFIG_FILE=config/enhanced_config.yaml"
    print_info "   - API_PORT=$PORT"
    print_info ""
    print_info "Option 2: Get full Lightsail permissions"
    print_info "1. Go to AWS IAM Console: https://console.aws.amazon.com/iam/"
    print_info "2. Click on 'Users' and select your user"
    print_info "3. Click 'Add permissions' and then 'Attach policies directly'"
    print_info "4. Search for 'AmazonLightsailFullAccess' and attach it"
    print_info "5. Click 'Next' and then 'Add permissions'"
    print_info "6. Wait a few minutes for permissions to propagate"
    print_info "7. Run this script again"
    print_info ""
    
    read -p "Would you like to continue with limited functionality? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

if [ "$HAS_PERMISSIONS" = true ]; then
    # Create a Lightsail container service if it doesn't exist
    print_info "Checking if container service exists..."
    if ! aws lightsail get-container-services --service-name $SERVICE_NAME --region $REGION &> /dev/null; then
        print_info "Creating Lightsail container service: $SERVICE_NAME"
        if ! aws lightsail create-container-service \
            --service-name $SERVICE_NAME \
            --power $BUNDLE_ID \
            --scale 1 \
            --region $REGION; then
            
            print_error "Failed to create container service. Check your AWS permissions."
            exit 1
        fi
        
        # Wait for the service to be ready
        print_info "Waiting for the service to be ready..."
        aws lightsail wait container-service-is-active \
            --service-name $SERVICE_NAME \
            --region $REGION
    else
        print_info "Container service $SERVICE_NAME already exists."
    fi

    # Push the container image to Lightsail
    print_info "Pushing container image to Lightsail..."
    if ! aws lightsail push-container-image \
        --service-name $SERVICE_NAME \
        --label cashflow \
        --image cashflow-trading \
        --region $REGION; then
        
        print_error "Failed to push container image. Check your AWS permissions."
        exit 1
    fi

    # Get the latest image
    print_info "Getting the latest image..."
    IMAGE_INFO=$(aws lightsail get-container-images \
        --service-name $SERVICE_NAME \
        --region $REGION 2>/dev/null)

    if [ $? -ne 0 ]; then
        print_error "Failed to get container images. Check your AWS permissions."
        print_info "Using a placeholder image name for the deployment JSON."
        IMAGE="${SERVICE_NAME}.cashflow.latest"
    else
        IMAGE=$(echo $IMAGE_INFO | jq -r '.containerImages[0].image' 2>/dev/null)
        if [ -z "$IMAGE" ] || [ "$IMAGE" == "null" ]; then
            print_warning "Could not parse image name. Using a placeholder."
            IMAGE="${SERVICE_NAME}.cashflow.latest"
        fi
    fi
else
    # Save the Docker image to a tar file for manual upload
    print_info "Saving Docker image to cashflow-trading.tar for manual upload..."
    docker save -o cashflow-trading.tar cashflow-trading
    
    if [ $? -eq 0 ]; then
        print_success "Docker image saved successfully to cashflow-trading.tar"
        print_info "You can manually upload this image to AWS Lightsail via the console."
    else
        print_error "Failed to save Docker image."
        exit 1
    fi
    
    # Set a placeholder image name for documentation purposes
    IMAGE="${SERVICE_NAME}.cashflow.latest"
    
    print_info ""
    print_info "Since you have limited permissions, follow these steps to deploy manually:"
    print_info "1. Go to AWS Lightsail Console: https://console.aws.amazon.com/lightsail/"
    print_info "2. Click on 'Containers'"
    print_info "3. Click 'Create container service'"
    print_info "4. Select 'Micro' ($BUNDLE_ID) with 1 node"
    print_info "5. Name your service '$SERVICE_NAME'"
    print_info "6. After creation, click 'Upload container image'"
    print_info "7. Upload the cashflow-trading.tar file"
    print_info "8. Configure with port $PORT and environment variables:"
    print_info "   - CONFIG_FILE=config/enhanced_config.yaml"
    print_info "   - API_PORT=$PORT"
    print_info "9. Set the public endpoint to port $PORT with path /status for health checks"
    print_info ""
fi

if [ "$HAS_PERMISSIONS" = true ]; then
    # Create deployment JSON
    print_info "Creating deployment configuration..."
    cat > deployment.json << EOF
{
  "containers": {
    "cashflow-app": {
      "image": "$IMAGE",
      "ports": {
        "$PORT": "HTTP"
      },
      "environment": {
        "CONFIG_FILE": "config/enhanced_config.yaml",
        "API_PORT": "$PORT"
      }
    }
  },
  "publicEndpoint": {
    "containerName": "cashflow-app",
    "containerPort": $PORT,
    "healthCheck": {
      "path": "/status",
      "intervalSeconds": 30,
      "timeoutSeconds": 10,
      "unhealthyThreshold": 3,
      "healthyThreshold": 3
    }
  }
}
EOF

    # Deploy to Lightsail
    print_info "Deploying to Lightsail..."
    if ! aws lightsail create-container-service-deployment \
        --service-name $SERVICE_NAME \
        --containers file://deployment.json \
        --public-endpoint file://deployment.json \
        --region $REGION; then
        
        print_error "Failed to create deployment. Check your AWS permissions."
        print_info ""
        print_info "If you're seeing permission errors, you need to add these permissions to your IAM user:"
        print_info "- lightsail:CreateContainerServiceDeployment"
        print_info ""
        print_info "You can still manually deploy through the AWS Lightsail Console:"
        print_info "1. Go to AWS Lightsail Console: https://console.aws.amazon.com/lightsail/"
        print_info "2. Navigate to Containers"
        print_info "3. Select your container service"
        print_info "4. Click 'Deploy new deployment'"
        print_info "5. Upload your Docker image or use the image you pushed"
        print_info "6. Configure the container with port $PORT"
        print_info "7. Set environment variables CONFIG_FILE=config/enhanced_config.yaml and API_PORT=$PORT"
        print_info "8. Deploy"
        
        # Clean up deployment.json
        rm -f deployment.json
        exit 1
    fi

    print_info "Deployment initiated. It may take a few minutes to complete."
    print_info "You can check the status with: aws lightsail get-container-services --service-name $SERVICE_NAME"

    # Wait for deployment to complete
    print_info "Waiting for deployment to complete..."
    if ! aws lightsail wait container-service-is-active \
        --service-name $SERVICE_NAME \
        --region $REGION; then
        
        print_warning "Timed out waiting for deployment to complete."
        print_info "The deployment may still be in progress."
        print_info "Check the status in the AWS Lightsail Console."
    fi

    # Get the public URL
    URL_INFO=$(aws lightsail get-container-services \
        --service-name $SERVICE_NAME \
        --region $REGION 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$URL_INFO" ]; then
        print_warning "Could not retrieve the public URL."
        print_info "Once the deployment is complete, you can find the URL in the AWS Lightsail Console."
        print_info "Your Cashflow Trading Agent API endpoints will be:"
        print_info "  - Status: https://<your-lightsail-url>/status"
        print_info "  - Debug: https://<your-lightsail-url>/debug"
        print_info "  - Portfolio: https://<your-lightsail-url>/portfolio"
        print_info "  - Start Trading: https://<your-lightsail-url>/start (POST)"
        print_info "  - Stop Trading: https://<your-lightsail-url>/stop (POST)"
        
        # Clean up deployment.json
        rm -f deployment.json
        exit 0
    fi

    URL=$(echo "$URL_INFO" | jq -r '.containerServices[0].url' 2>/dev/null)

    if [ -z "$URL" ] || [ "$URL" == "null" ]; then
        print_warning "Could not parse the public URL from the response."
        print_info "Once the deployment is complete, you can find the URL in the AWS Lightsail Console."
    else
        print_success "Deployment completed successfully!"
        print_info "Your Cashflow Trading Agent is now available at: $URL"
        print_info "API Endpoints:"
        print_info "  - Status: $URL/status"
        print_info "  - Debug: $URL/debug"
        print_info "  - Portfolio: $URL/portfolio"
        print_info "  - Start Trading: $URL/start (POST)"
        print_info "  - Stop Trading: $URL/stop (POST)"
    fi

    # Clean up deployment.json
    rm -f deployment.json
else
    # Create a manual deployment guide
    print_info "Creating manual deployment guide..."
    
    cat > manual-deployment-guide.md << EOF
# Manual Deployment Guide for Cashflow Trading Agent

## Prerequisites
- AWS account with access to Lightsail
- Docker image saved as cashflow-trading.tar

## Deployment Steps

1. **Create a Container Service**
   - Go to AWS Lightsail Console: https://console.aws.amazon.com/lightsail/
   - Click on 'Containers'
   - Click 'Create container service'
   - Select 'Micro' ($BUNDLE_ID) with 1 node
   - Name your service '$SERVICE_NAME'
   - Click 'Create'

2. **Upload Container Image**
   - After the service is created, click on it
   - Click 'Upload container image'
   - Upload the cashflow-trading.tar file
   - Wait for the upload to complete

3. **Create Deployment**
   - Click 'Create deployment'
   - Select the uploaded image
   - Set container name to 'cashflow-app'
   - Configure port $PORT as HTTP
   - Add environment variables:
     - CONFIG_FILE=config/enhanced_config.yaml
     - API_PORT=$PORT
   - Set the public endpoint to container 'cashflow-app', port $PORT
   - Configure health check to path '/status'
   - Click 'Deploy'

4. **Access Your Trading Agent**
   Once deployed, your Cashflow Trading Agent will be available at the URL provided by Lightsail.
   
   API Endpoints:
   - Status: https://<your-lightsail-url>/status
   - Debug: https://<your-lightsail-url>/debug
   - Portfolio: https://<your-lightsail-url>/portfolio
   - Start Trading: https://<your-lightsail-url>/start (POST)
   - Stop Trading: https://<your-lightsail-url>/stop (POST)

## Monitoring and Management

- View logs: In the Lightsail console, select your container service and click on 'Logs'
- Restart: Click on 'Deployments' and then 'Create deployment' to redeploy
- Scale: Under 'Capacity' you can adjust the number of nodes

## Troubleshooting

- If the health check fails, verify that the application is running correctly by checking the logs
- Ensure the port and environment variables are correctly configured
- If needed, you can SSH into the container to debug by clicking on 'Connect'

EOF

    print_success "Manual deployment guide created: manual-deployment-guide.md"
    print_info "Follow the instructions in this guide to manually deploy your Cashflow Trading Agent."
    print_info "The Docker image has been saved to cashflow-trading.tar for manual upload."
    
    # Create a sample deployment JSON for reference
    cat > sample-deployment.json << EOF
{
  "containers": {
    "cashflow-app": {
      "image": "$IMAGE",
      "ports": {
        "$PORT": "HTTP"
      },
      "environment": {
        "CONFIG_FILE": "config/enhanced_config.yaml",
        "API_PORT": "$PORT"
      }
    }
  },
  "publicEndpoint": {
    "containerName": "cashflow-app",
    "containerPort": $PORT,
    "healthCheck": {
      "path": "/status",
      "intervalSeconds": 30,
      "timeoutSeconds": 10,
      "unhealthyThreshold": 3,
      "healthyThreshold": 3
    }
  }
}
EOF

    print_info "A sample deployment configuration has been saved to sample-deployment.json for reference."
fi
