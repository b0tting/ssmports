import pytest
from unittest.mock import MagicMock

from src.ecs_id_resolver import ECSIDResolver


class TestECSIDResolver:
    def test_resolve_task_name_found(self):
        resolver = ECSIDResolver()
        mock_ecs_client = MagicMock()
        mock_ecs_client.list_clusters.return_value = {
            "clusterArns": ["arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster"]
        }
        mock_ecs_client.list_tasks.return_value = {
            "taskArns": [
                "arn:aws:ecs:us-east-1:123456789012:task/my-cluster/12345678901234567890123456789012"
            ]
        }
        mock_task_desc = {
            "tasks": [
                {
                    "containers": [
                        {
                            "name": "my-container",
                            "runtimeId": "12345678901234567890123456789012",
                        }
                    ]
                }
            ]
        }
        mock_ecs_client.describe_tasks.return_value = mock_task_desc

        result = resolver.resolve_task_name("my-container", mock_ecs_client)
        expected = "ecs:my-cluster_12345678901234567890123456789012_12345678901234567890123456789012"
        assert result == expected

    def test_resolve_task_name_cached(self):
        resolver = ECSIDResolver()
        mock_ecs_client = MagicMock()
        # First call
        mock_ecs_client.list_clusters.return_value = {
            "clusterArns": ["arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster"]
        }
        mock_ecs_client.list_tasks.return_value = {
            "taskArns": [
                "arn:aws:ecs:us-east-1:123456789012:task/my-cluster/12345678901234567890123456789012"
            ]
        }
        mock_task_desc = {
            "tasks": [
                {
                    "containers": [
                        {
                            "name": "my-container",
                            "runtimeId": "12345678901234567890123456789012",
                        }
                    ]
                }
            ]
        }
        mock_ecs_client.describe_tasks.return_value = mock_task_desc

        resolver.resolve_task_name("my-container", mock_ecs_client)
        # Second call should use cache
        result = resolver.resolve_task_name("my-container", mock_ecs_client)
        expected = "ecs:my-cluster_12345678901234567890123456789012_12345678901234567890123456789012"
        assert result == expected
        # list_clusters should only be called once
        assert mock_ecs_client.list_clusters.call_count == 1

    def test_resolve_task_name_not_found(self):
        resolver = ECSIDResolver()
        mock_ecs_client = MagicMock()
        mock_ecs_client.list_clusters.return_value = {
            "clusterArns": ["arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster"]
        }
        mock_ecs_client.list_tasks.return_value = {
            "taskArns": [
                "arn:aws:ecs:us-east-1:123456789012:task/my-cluster/12345678901234567890123456789012"
            ]
        }
        mock_task_desc = {
            "tasks": [
                {
                    "containers": [
                        {
                            "name": "other-container",
                            "runtimeId": "12345678901234567890123456789012",
                        }
                    ]
                }
            ]
        }
        mock_ecs_client.describe_tasks.return_value = mock_task_desc

        with pytest.raises(ValueError, match="Task name 'my-container' not found"):
            resolver.resolve_task_name("my-container", mock_ecs_client)

    def test_resolve_task_name_multiple_clusters(self):
        resolver = ECSIDResolver()
        mock_ecs_client = MagicMock()
        mock_ecs_client.list_clusters.return_value = {
            "clusterArns": [
                "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
                "arn:aws:ecs:us-east-1:123456789012:cluster/cluster2",
            ]
        }
        mock_ecs_client.list_tasks.side_effect = [
            {"taskArns": ["arn:aws:ecs:us-east-1:123456789012:task/cluster1/task1"]},
            {"taskArns": ["arn:aws:ecs:us-east-1:123456789012:task/cluster2/task2"]},
        ]
        mock_task_desc1 = {
            "tasks": [
                {"containers": [{"name": "other-container", "runtimeId": "runtime1"}]}
            ]
        }
        mock_task_desc2 = {
            "tasks": [
                {"containers": [{"name": "my-container", "runtimeId": "runtime2"}]}
            ]
        }
        mock_ecs_client.describe_tasks.side_effect = [mock_task_desc1, mock_task_desc2]

        result = resolver.resolve_task_name("my-container", mock_ecs_client)
        expected = "ecs:cluster2_task2_runtime2"
        assert result == expected
