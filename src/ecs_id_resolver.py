class ECSIDResolver:
    def __init__(self):
        self.found_ids = {}

    def resolve_task_name(self, task_name, ecs_client):
        """
        Given a container name, enumerate over all the ECS clusters and generate an ECS instance ID usable
        for SSM Session Manager: ecs_<cluster_name>_<task_id>_<container_id>
        """
        if task_name in self.found_ids:
            return self.found_ids[task_name]

        clusters = ecs_client.list_clusters()["clusterArns"]
        for cluster_arn in clusters:
            cluster_name = cluster_arn.split("/")[-1]
            tasks = ecs_client.list_tasks(cluster=cluster_arn)["taskArns"]
            for task_arn in tasks:
                task_id = task_arn.split("/")[-1]
                task_desc = ecs_client.describe_tasks(
                    cluster=cluster_arn, tasks=[task_arn]
                )["tasks"][0]
                for container in task_desc.get("containers", []):
                    if container.get("name") == task_name:
                        container_id = container.get("runtimeId")
                        ecs_instance_id = f"ecs:{cluster_name}_{task_id}_{container_id}"
                        self.found_ids[task_name] = ecs_instance_id
                        return ecs_instance_id
        else:
            raise ValueError(f"Task name '{task_name}' not found in any ECS cluster.")
