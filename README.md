# SSM Port Forwarder

A graphical user interface for managing multiple AWS Systems Manager (SSM) port forwarding sessions simultaneously. This tool simplifies connecting to remote hosts (like RDS instances or EC2 private services) through an SSM-enabled bastion host.

Some key features:
- **Multi-session Management**: Start and stop multiple port forwarding tunnels at once.
- **Profile Support**: Use different AWS profiles for each connection.
- **Link Integration**: Define clickable links (e.g., for web consoles)

[![SSM Port Forwarder Screenshot](img/screenshot.png)](img/screenshot.png)

## Attribution
The core code was based on a Github request (https://github.com/boto/boto3/issues/3555) made by @JGoutin 

## Preparing Your Environment

### Prerequisites

Before using this tool, ensure you have the following installed and configured:

1.  **Python 3.12+**: Ensure Python is installed on your system.
2.  **AWS CLI**: Installed and configured.
3.  **SSM Session Manager Plugin**: This is required by AWS to handle the tunnel. [Install instructions here](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
4.  **Dependencies**: Either use Poetry or install required Python packages with PIP:
    ```bash
    pip install boto3 jsonschema
    ```

### AWS Authentication with saml2aws

#### Role configuration
If your role has admin access or a broad policy this won't be required, but if not: Your role needs access to the startSession permission and specifically to the `ssm:StartSession` action. Here is an example IAM policy as taken from https://repost.aws/questions/QUMa9_kum3Sk-fg4TL6sPfZg/policy-for-ssm-port-forwarding-session-to-remote-host:  

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:StartSession"
            ],
            "Resource": [
                "arn:aws:ec2:ap-southeast-1:yyyyyyyyyyy:instance/i-55555555555555555",
                "arn:aws:ssm:ap-southeast-1:yyyyyyyyyyy:document/SSM-SessionManagerRunShell",
                "arn:aws:ssm:ap-southeast-1::document/AWS-StartPortForwardingSessionToRemoteHost"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:TerminateSession",
                "ssm:ResumeSession"
            ],
            "Resource": [
                "arn:aws:ssm:*:*:session/${aws:userid}-*"
            ]
        },{
          "Sid": "AllowContainerIdLookup",
          "Effect": "Allow",
            "Action": [
                "ecs:ListClusters",
                "ecs:DescribeClusters",
                "ecs:ListTasks",
                "ecs:DescribeTasks",
                "ecs:DescribeContainerInstances"
            ],
            "Resource": "*"
      }
    ]
}
```

If your organization uses SAML-based authentication (like Okta or AD FS), it is recommended to use `saml2aws` to manage your credentials.

1.  **Configure saml2aws**: Run `saml2aws configure` to set up your identity provider details.
2.  **Login**: Before starting the SSM Port Forwarder, authenticate using:
    ```bash
    saml2aws login --profile your-profile-name
    ```
3.  **Verification**: Ensure your credentials are active by running `aws sts get-caller-identity --profile your-profile-name`.

The SSM Port Forwarder will automatically use the active credentials for the profiles specified in your configuration.

## Configuring sessions.json

The application relies on a `sessions.json` file in the root directory to define your connections. A template is provided in `sessions.json.example`.

### Example Configuration

This is a simple configuration that defines a single connection to a production database through a bastion host:
```json
{
  "connections": {
    "Production Database": {
      "target_host": "prod-db.cluster-xxxx.eu-west-1.rds.amazonaws.com",
      "local_port": 5432,
      "remote_port": 5432,
      "profile": "my-default-profile",
      "region": "eu-west-1",
      "jump_instance": "i-0123456789abcdef0"
    }
  }
}
```

You can also pull up the profile, region and jump instance from your AWS configuration to set them as defaults. The jump_instance can be either an EC2 instance ID, an ECS instance ID (see https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html#sessions-remote-port-forwarding) or a specific container name. 

If a container name is used the tool will attempt to resolve the container to the underlying EC2 instance ID, optionally using the profile and region provided. It will take the first result if multiple containers with the same name are found.

Here is a more complete example:
```json
{
  "profile": "my-jump-account",
  "region": "eu-west-1",
  "jump_instance": "my-bastion-container",
  "connections": {
    "Production Database": {
      "target_host": "prod-db.cluster-xxxx.eu-west-1.rds.amazonaws.com",
      "local_port": 5432,
      "remote_port": 5432
    },
    "Staging Database": {
      "target_host": "test-db.cluster-xxxx.eu-west-1.rds.amazonaws.com",
      "local_port": 5433,
      "remote_port": 5432,
      "profile": "my-test-account",
      "jump_instance": "ecs:my-cluster_12345678901234567890123456789012_12345678901234567890123456789012-0151737364"
    }
  }
}
```

### Attributes

| Attribute       | Level             | Required | Description                                                                                                         |
|:----------------|:------------------| :--- |:--------------------------------------------------------------------------------------------------------------------|
| `connections`   | Root              | Yes | A dictionary of connection objects. The key is the label shown in the UI.                                           |
| `target_host`   | Connection        | Yes | The remote hostname or IP to connect to (e.g., RDS endpoint).                                                       |
| `local_port`    | Connection        | Yes | The port on your local machine to bind the tunnel to.                                                               |
| `remote_port`   | Connection        | Yes | The port on the remote host to forward to.                                                                          |
| `jump_instance` | Connection / Root | Yes | The ID of the SSM-enabled EC2 instance acting as the bastion.                                                       |
| `profile`       | Connection / Root | No | AWS Profile to use to connect to the jump instance                                                                  |
| `region`        | Connection / Root | No | AWS Region for the jump instance                                                                                    |
| `link`          | Connection        | No | A URL that will appear as a clickable "Open Link" button. Supports `{local_port}` and `{remote_port}` placeholders. |
| `autostart`     | Connection        | No | If `true`, the session starts automatically when the GUI launches.                                                  |

## Usage

1.  Create your `sessions.json` file (you can use `sessions.json.example` as a starting point).
2.  Authenticate with AWS (e.g., using `saml2aws login`).
3.  Run the application:
    ```bash
    python gui.py
    ```
4.  Click **Start** to open a tunnel.
5.  Click **Open Link** (if configured) to access the service.
6.  Click **Reload Config** if you make changes to `sessions.json` while the app is running.

## Building a Standalone Executable

To create a standalone executable that doesn't require Python to be installed:

1. Ensure you have the development dependencies installed:
   ```bash
   poetry install --with dev
   ```

2. Run the build script:
   ```bash
   build.bat
   ```

   Or manually:
   ```bash
   pip install https://github.com/pyinstaller/pyinstaller/archive/develop.zip
   pyinstaller ssmports.spec
   ```

3. The executable will be created in the `dist/` directory as `ssmports.exe`.

Note: The executable includes all necessary dependencies and data files, making it portable.
