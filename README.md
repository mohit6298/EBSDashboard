# AWS EBS Monitoring Dashboard Generator

A comprehensive Python-based tool for automatically generating CloudWatch dashboards to monitor Amazon EBS (Elastic Block Store) volumes attached to EC2 instances. The tool creates detailed dashboards with IOPS and throughput metrics for each volume.

## Features

- **Automatic Dashboard Generation**
  - Creates CloudWatch dashboards for EBS volumes
  - Monitors IOPS and throughput for each volume
  - Supports multiple volumes per instance
  - Real-time metric visualization

- **Volume Metrics**
  - IOPS monitoring with actual volume limits
  - Throughput tracking with volume-specific thresholds
  - Automatic volume discovery for EC2 instances
  - Support for named volumes via tags

- **Interactive Setup**
  - Region selection from available AWS regions
  - EC2 instance selection
  - Custom dashboard naming
  - Volume name customization

- **Visual Enhancements**
  - Progress bars for long-running operations
  - Colored console output for better readability
  - Clear error messages and status updates

## Prerequisites

- Python 3.6 or higher
- AWS credentials configured (`~/.aws/credentials` or environment variables)
- Required Python packages (see `requirements.txt`):
  ```
  boto3>=1.26.137,<2.0.0
  colorama>=0.4.6,<1.0.0
  tqdm>=4.65.0,<5.0.0
  ```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/mohit6298/EBSDashboard.git
   cd EBSDashboard
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

Run the script:

```bash
python ebs_dashboard_generator.py
```

### Interactive Process

1. Select AWS Region:
   - Choose from the list of available regions
   - Validates region selection

2. Provide EC2 Instance ID:
   - Enter the ID of the target EC2 instance
   - Format: i-xxxxxxxxxxxxxxxxx
   - Validates instance ID format

3. Set Dashboard Name:
   - Enter a custom name for the CloudWatch dashboard
   - Used for easy identification in CloudWatch

4. Volume Configuration:
   - Automatically discovers attached EBS volumes
   - Uses volume tags if available
   - Allows custom naming for untagged volumes

## Dashboard Features

### IOPS Metrics
- Combined read and write operations
- Actual IOPS limit visualization
- 1-minute granularity
- Automatic scaling

### Throughput Metrics
- Combined read and write throughput
- Volume-specific throughput limits
- Byte-based measurements
- Automatic unit conversion

## Required AWS Permissions

The following IAM permissions are required:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVolumes",
                "ec2:DescribeRegions",
                "cloudwatch:PutDashboard",
                "cloudwatch:GetDashboard"
            ],
            "Resource": "*"
        }
    ]
}
```

## Error Handling

The script includes comprehensive error handling for:
- AWS API failures
- Invalid user inputs
- Resource access issues
- Network connectivity problems

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request


## Support

For support:
1. Open an issue in the repository
2. Include:
   - Script version
   - Python version
   - AWS region
   - Error message (if applicable)
   - Steps to reproduce

## Security Notes

- Never commit AWS credentials
- Use IAM roles when possible
- Regularly rotate access keys
- Follow AWS security best practices

## Acknowledgments

- AWS SDK for Python (Boto3)
- CloudWatch Metrics API
- EC2 API