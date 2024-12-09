import json
import boto3
from typing import Dict, List, Optional

def get_volume_details(ec2_client, volume_id: str) -> Dict:
    """Get detailed information about a specific volume."""
    response = ec2_client.describe_volumes(VolumeIds=[volume_id])
    if response['Volumes']:
        volume = response['Volumes'][0]
        name_tag = next((tag['Value'] for tag in volume.get('Tags', []) 
                        if tag['Key'] == 'Name'), None)
        return {
            'name_tag': name_tag,
            'iops': volume.get('Iops', 3000),  # Default for gp3
            'throughput': volume.get('Throughput', 125)  # Default for gp3 in MB/s
        }
    return {'name_tag': None, 'iops': 3000, 'throughput': 125}

def generate_iops_widget(volume_id: str, drive_name: str, region: str, iops: int) -> Dict:
    """Generate IOPS widget configuration with actual IOPS limit."""
    return {
        "metrics": [
            [{"expression": "(m1+m2)/(60-m3)", "label": "Expression1", "id": "e1", "region": region}],
            ["AWS/EBS", "VolumeReadOps", "VolumeId", volume_id, 
             { "id": "m1", "visible": False, "region": region }],
            [".", "VolumeWriteOps", ".", ".", 
             { "id": "m2", "visible": False, "region": region }],
            [".", "VolumeIdleTime", ".", ".", 
             { "id": "m3", "visible": False, "region": region }]
        ],
        "view": "timeSeries",
        "stacked": False,
        "region": region,
        "stat": "Sum",
        "period": 60,
        "title": f"IOPS - {volume_id}_{drive_name}",
        "annotations": {
            "horizontal": [
                {
                    "value": iops,
                    "fill": "below"
                }
            ]
        }
    }

def generate_throughput_widget(volume_id: str, drive_name: str, region: str, throughput: int) -> Dict:
    """Generate throughput widget configuration with actual throughput limit."""
    # Convert throughput from MB/s to Bytes/s
    throughput_bytes = throughput * 1024 * 1024
    
    return {
        "sparkline": True,
        "metrics": [
            [{"expression": "(m1+m2)/(60-m3)", "label": "Expression1", "id": "e1", 
              "period": 60, "stat": "Sum", "region": region}],
            ["AWS/EBS", "VolumeReadBytes", "VolumeId", volume_id, 
             {"id": "m1", "visible": False, "region": region}],
            [".", "VolumeWriteBytes", ".", ".", 
             {"id": "m2", "visible": False, "region": region}],
            [".", "VolumeIdleTime", ".", ".", 
             {"id": "m3", "visible": False, "region": region}]
        ],
        "view": "timeSeries",
        "stacked": False,
        "region": region,
        "stat": "Sum",
        "period": 60,
        "yAxis": {
            "left": {
                "min": 0
            }
        },
        "liveData": False,
        "singleValueFullPrecision": False,
        "setPeriodToTimeRange": True,
        "title": f"Throughput - {volume_id}_{drive_name}",
        "annotations": {
            "horizontal": [
                {
                    "value": throughput_bytes,
                    "fill": "below"
                }
            ]
        }
    }

class EBSDashboardGenerator:
    def __init__(self, region: str):
        print("Initializing AWS clients...")
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)

    def get_volume_info(self, instance_id: str) -> List[Dict]:
        """Get all volumes attached to an EC2 instance with their details."""
        volumes = []
        
        try:
            print("Fetching EBS volumes...")
            response = self.ec2_client.describe_volumes(
                Filters=[{
                    'Name': 'attachment.instance-id',
                    'Values': [instance_id]
                }]
            )
            
            for volume in response['Volumes']:
                device_name = volume['Attachments'][0]['Device']
                volume_details = get_volume_details(self.ec2_client, volume['VolumeId'])
                volumes.append({
                    'VolumeId': volume['VolumeId'],
                    'DeviceName': device_name,
                    'Size': volume['Size'],
                    'NameTag': volume_details['name_tag'],
                    'Iops': volume_details['iops'],
                    'Throughput': volume_details['throughput']
                })
            
            return volumes
            
        except Exception as e:
            print(f"Error getting volume information: {str(e)}")
            return []

    def get_drive_names(self, volumes: List[Dict]) -> Dict[str, str]:
        """Get drive names from tags or user input."""
        drive_names = {}
        
        print("Collecting drive names for volumes:")
        print("=" * 60)
        
        for volume in volumes:
            volume_id = volume['VolumeId']
            size = volume['Size']
            device_name = volume['DeviceName']
            name_tag = volume['NameTag']
            
            print("\nVolume Details:")
            print(f"Volume ID: {volume_id}")
            print(f"Device Name: {device_name}")
            print(f"Size: {size} GB")
            
            if name_tag:
                print(f"Using name from tag: {name_tag}")
                drive_names[volume_id] = name_tag
            else:
                while True:
                    drive_name = input("Enter drive name for this volume (e.g., SYSDB, DATA): ").strip()
                    if drive_name:
                        drive_names[volume_id] = drive_name
                        break
                    print("Drive name cannot be empty. Please try again.")
                
        return drive_names

    def create_dashboard(self, instance_id: str, dashboard_name: str) -> None:
        """Create or update CloudWatch dashboard for all volumes attached to an instance."""
        try:
            volumes = self.get_volume_info(instance_id)
            if not volumes:
                print(f"No volumes found for instance {instance_id}")
                return
                
            print(f"Found {len(volumes)} volumes attached to instance {instance_id}")
            
            drive_names = self.get_drive_names(volumes)
            
            print("Generating dashboard widgets...")
            widgets = []
            
            for volume in volumes:
                volume_id = volume['VolumeId']
                drive_name = drive_names[volume_id]
                
                widgets.extend([
                    {
                        "type": "metric",
                        "width": 12,
                        "height": 6,
                        "properties": generate_iops_widget(
                            volume_id, 
                            drive_name, 
                            self.cloudwatch_client.meta.region_name,
                            volume['Iops']
                        )
                    },
                    {
                        "type": "metric",
                        "width": 12,
                        "height": 6,
                        "properties": generate_throughput_widget(
                            volume_id, 
                            drive_name, 
                            self.cloudwatch_client.meta.region_name,
                            volume['Throughput']
                        )
                    }
                ])

            dashboard_body = {
                "widgets": widgets
            }

            print("Creating CloudWatch dashboard...")
            self.cloudwatch_client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            print(f"Successfully created/updated dashboard: {dashboard_name}")
            
        except self.ec2_client.exceptions.ClientError as e:
            print(f"AWS API Error: {str(e)}")
        except Exception as e:
            print(f"Error: {str(e)}")

def get_aws_regions() -> List[str]:
    """Get list of available AWS regions."""
    try:
        print("Fetching AWS regions...")
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        return [region['RegionName'] for region in response['Regions']]
    except Exception as e:
        print(f"Error fetching AWS regions: {str(e)}")
        return ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'eu-west-1']

def get_user_inputs() -> tuple:
    """Get user inputs for instance ID, region, and dashboard name."""
    print("\n*************************************************************************")
    print("*************** Welcome to EBS Dashboard Generator! *********************")
    print("*************************************************************************")
    
    regions = get_aws_regions()
    print("\nAvailable AWS regions:")
    for i, region in enumerate(regions, 1):
        print(f"{i}. {region}")
    
    while True:
        try:
            region_index = int(input("\nSelect region number: ")) - 1
            if 0 <= region_index < len(regions):
                selected_region = regions[region_index]
                break
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    while True:
        instance_id = input("\nEnter EC2 instance ID (e.g., i-0123456789abcdef0): ").strip()
        if instance_id.startswith('i-') and len(instance_id) > 2:
            break
        print("Invalid instance ID format. Must start with 'i-'. Please try again.")
    
    while True:
        dashboard_name = input("\nEnter dashboard name: ").strip()
        if dashboard_name:
            break
        print("Dashboard name cannot be empty. Please try again.")
    
    return instance_id, selected_region, dashboard_name

def main():
    try:
        instance_id, region, dashboard_name = get_user_inputs()
        
        print("\nSummary of inputs:")
        print(f"Instance ID: {instance_id}")
        print(f"Region: {region}")
        print(f"Dashboard Name: {dashboard_name}")
        
        confirm = input("\nProceed with these settings? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nOperation cancelled by user.")
            return
        
        generator = EBSDashboardGenerator(region)
        generator.create_dashboard(instance_id, dashboard_name)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()