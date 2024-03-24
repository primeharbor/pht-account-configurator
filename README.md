# pht-account-configurator
Configure a new AWS Account with security best practices


When a new AWS account is created via AWS Organizations, a number of AWS recommended best-practices are _NOT_ enabled. This StepFunction listens for EventBridge events indicating a new account was created and configures the account according to your preferences.

What the Stepfunction does:
1. Sets a CIS compliant IAM Password policy. You shouldn't be using IAM Users, but this shuts up any CSPM checks.
2. Enables Account Wide S3 Block Public Access to ensure all S3 buckets aren't public.
    1. Use this in conjunction with an SCP to prevent removal of this setting and force all public S3 Buckets into a dedicated AWS Account
3. Enables Block Public Access for all EBS Snapshots in all the enabled regions.
4. Enables EBS Default Encryption for all EBS Volumes in all the enabled regions.
5. Deletes all the default VPCs in all the regions (except the regions marked for preservation)
    1. Note: This will not delete any VPCs with an ENI in it.

This stepfunction can be run _after_ account creation, however their are a few risks:
1. By blocking all S3 public access you may break public S3 buckets.
2. Custom KMS keys for EBS Default Encryption may be overwritten.


## Configuration

The Lambda functions are controlled by the following config file. If a section is not present the configuration is not applied.

```yaml
# Configure the IAM Password Policy per CIS Benchmarks
# https://docs.aws.amazon.com/securityhub/latest/userguide/iam-controls.html#iam-10
account_password_policy:
  update_account_password_policy: true
  # Note: all of the following must be present
  password_policy:
      MinimumPasswordLength: 24
      RequireSymbols: True
      RequireNumbers: True
      RequireUppercaseCharacters: True
      RequireLowercaseCharacters: True
      AllowUsersToChangePassword: True
      MaxPasswordAge: 90
      PasswordReusePrevention: 24
      HardExpiry: False

# Delete Default VPCs
default_vpc:
  delete_default_vpc: true
  # Regions in this list will not have their default VPCs created
  preserve_vpc_regions:
    - "us-east-1"
    - "eu-central-1"

# Enable Default Encryption of EBS in all enabled regions
enable_ebs_default_encryption: true

# Enable Block Public Access for EBS snapshots in all enabled regions
enable_ebs_block_public_access: true

# Enable Account Wide S3 Block Public Access
enable_account_s3_block_public_access:
    BlockPublicAcls: True
    IgnorePublicAcls: True
    BlockPublicPolicy: True
    RestrictPublicBuckets: true
```

## Deployment

1. Create an S3 bucket to store the Lambda configuration and config file:
```bash
export DEPLOY_BUCKET=pht-account-configurator
aws s3 mb s3://$DEPLOY_BUCKET
```
2. Deploy the CloudFormation Stack
```bash
make deploy
```
3. Adjust the config file and copy it to S3
```bash
cat account-factory-config.yaml
make push-config
```
4. Test with a sandbox or new account. See warning above.
```bash
make test-trigger ACCOUNT_ID=123456789012
```

Review the contents of the [cloudformation/AccountFactory-Manifest.yaml](cloudformation/AccountFactory-Manifest.yaml) file to ensure it meets your naming conventions, and apply any additional tags. If you wish to use your own Manifest just add `export MANIFEST=my-Manifest.yaml` before running `make deploy`