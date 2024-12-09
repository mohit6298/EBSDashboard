import json
import boto3
import time
from typing import Dict, List, Optional
from colorama import init, Fore, Style
from tqdm import tqdm
import sys

# Initialize colorama for cross-platform color support
init()

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
        self.region = region
        print(f"\n{Fore.YELLOW}⚡ Initializing AWS clients...{Style.RESET_ALL}")
        with tqdm(total=2, bar_format='{l_bar}{bar}|') as pbar:
            self.ec2_client = boto3.client('ec2', region_name=region)
            pbar.update(1)
            self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
            pbar.update(1)

    def get_volume_info(self, instance_id: str) -> List[Dict]:
        """Get all volumes attached to an EC2 instance with their details."""
        volumes = []
        
        try:
            print(f"\n{Fore.CYAN}📡 Fetching EBS volumes...{Style.RESET_ALL}")
            with tqdm(total=1, bar_format='{l_bar}{bar}|') as pbar:
                response = self.ec2_client.describe_volumes(
                    Filters=[{
                        'Name': 'attachment.instance-id',
                        'Values': [instance_id]
                    }]
                )
                pbar.update(1)
            
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
            print(f"{Fore.RED}❌ Error getting volume information: {str(e)}{Style.RESET_ALL}")
            return []

    def get_drive_names(self, volumes: List[Dict]) -> Dict[str, str]:
        """Get drive names from tags or user input."""
        drive_names = {}
        
        print(f"\n{Fore.GREEN}📝 Collecting drive names for volumes:{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'=' * 60}{Style.RESET_ALL}")
        
        for volume in volumes:
            volume_id = volume['VolumeId']
            size = volume['Size']
            device_name = volume['DeviceName']
            name_tag = volume['NameTag']
            
            print(f"\n{Fore.YELLOW}Volume Details:{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Volume ID:{Style.RESET_ALL} {volume_id}")
            print(f"{Fore.CYAN}Device Name:{Style.RESET_ALL} {device_name}")
            print(f"{Fore.CYAN}Size:{Style.RESET_ALL} {size} GB")
            
            if name_tag:
                print(f"{Fore.GREEN}Using name from tag: {name_tag}{Style.RESET_ALL}")
                drive_names[volume_id] = name_tag
            else:
                while True:
                    drive_name = input(f"{Fore.GREEN}Enter drive name for this volume (e.g., SYSDB, DATA):{Style.RESET_ALL} ").strip()
                    if drive_name:
                        drive_names[volume_id] = drive_name
                        break
                    print(f"{Fore.RED}Drive name cannot be empty. Please try again.{Style.RESET_ALL}")
                
        return drive_names

    def create_dashboard(self, instance_id: str, dashboard_name: str) -> None:
        """Create or update CloudWatch dashboard for all volumes attached to an instance."""
        try:
            volumes = self.get_volume_info(instance_id)
            if not volumes:
                print(f"{Fore.RED}❌ No volumes found for instance {instance_id}{Style.RESET_ALL}")
                return
                
            print(f"\n{Fore.GREEN}✅ Found {len(volumes)} volumes attached to instance {instance_id}{Style.RESET_ALL}")
            
            drive_names = self.get_drive_names(volumes)
            
            print(f"\n{Fore.YELLOW}🔨 Generating dashboard widgets...{Style.RESET_ALL}")
            widgets = []
            
            with tqdm(total=len(volumes), desc="Processing volumes", bar_format='{l_bar}{bar}|') as pbar:
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
                                self.region,
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
                                self.region,
                                volume['Throughput']
                            )
                        }
                    ])
                    pbar.update(1)

            dashboard_body = {
                "widgets": widgets
            }

            print(f"\n{Fore.YELLOW}📊 Creating CloudWatch dashboard...{Style.RESET_ALL}")
            with tqdm(total=1, bar_format='{l_bar}{bar}|') as pbar:
                self.cloudwatch_client.put_dashboard(
                    DashboardName=dashboard_name,
                    DashboardBody=json.dumps(dashboard_body)
                )
                pbar.update(1)
            
            print(f"\n{Fore.GREEN}✅ Successfully created/updated dashboard: {dashboard_name}{Style.RESET_ALL}")
            
        except self.ec2_client.exceptions.ClientError as e:
            print(f"{Fore.RED}❌ AWS API Error: {str(e)}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")

def get_aws_regions() -> List[str]:
    """Get list of available AWS regions."""
    try:
        print(f"\n{Fore.YELLOW}🌍 Fetching AWS regions...{Style.RESET_ALL}")
        with tqdm(total=1, bar_format='{l_bar}{bar}|') as pbar:
            ec2_client = boto3.client('ec2', region_name='us-east-1')
            response = ec2_client.describe_regions()
            pbar.update(1)
        return [region['RegionName'] for region in response['Regions']]
    except Exception as e:
        print(f"{Fore.RED}❌ Error fetching AWS regions: {str(e)}{Style.RESET_ALL}")
        return ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'eu-west-1']

def get_user_inputs() -> tuple:
    """Get user inputs for instance ID, region, and dashboard name."""
    print(f"\n{Fore.CYAN}{'=' * 40}")
    print(f"🚀 Welcome to EBS Dashboard Generator!")
    print(f"{'=' * 40}{Style.RESET_ALL}")
    
    regions = get_aws_regions()
    print(f"\n{Fore.GREEN}Available AWS regions:{Style.RESET_ALL}")
    for i, region in enumerate(regions, 1):
        print(f"{Fore.YELLOW}{i}.{Style.RESET_ALL} {region}")
    
    while True:
        try:
            region_index = int(input(f"\n{Fore.GREEN}Select region number:{Style.RESET_ALL} ")) - 1
            if 0 <= region_index < len(regions):
                selected_region = regions[region_index]
                break
            print(f"{Fore.RED}Invalid selection. Please try again.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number.{Style.RESET_ALL}")
    
    while True:
        instance_id = input(f"\n{Fore.GREEN}Enter EC2 instance ID (e.g., i-0123456789abcdef0):{Style.RESET_ALL} ").strip()
        if instance_id.startswith('i-') and len(instance_id) > 2:
            break
        print(f"{Fore.RED}Invalid instance ID format. Must start with 'i-'. Please try again.{Style.RESET_ALL}")
    
    while True:
        dashboard_name = input(f"\n{Fore.GREEN}Enter dashboard name:{Style.RESET_ALL} ").strip()
        if dashboard_name:
            break
        print(f"{Fore.RED}Dashboard name cannot be empty. Please try again.{Style.RESET_ALL}")
    
    return instance_id, selected_region, dashboard_name

def main():
    try:
        instance_id, region, dashboard_name = get_user_inputs()
        
        print(f"\n{Fore.CYAN}📋 Summary of inputs:{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Instance ID:{Style.RESET_ALL} {instance_id}")
        print(f"{Fore.YELLOW}Region:{Style.RESET_ALL} {region}")
        print(f"{Fore.YELLOW}Dashboard Name:{Style.RESET_ALL} {dashboard_name}")
        
        confirm = input(f"\n{Fore.GREEN}Proceed with these settings? (y/n):{Style.RESET_ALL} ").strip().lower()
        if confirm != 'y':
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
            return
        
        generator = EBSDashboardGenerator(region)
        generator.create_dashboard(instance_id, dashboard_name)
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()