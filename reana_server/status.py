# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Status module for REANA."""

import subprocess
from datetime import datetime, timedelta

from invenio_accounts.models import SessionActivity
from reana_commons.config import SHARED_VOLUME_PATH
from reana_db.database import Session
from reana_db.models import (
    Workflow,
    RunStatus,
    InteractiveSession,
    User,
    Resource,
    UserResource,
    ResourceType,
    ResourceUnit,
)
from sqlalchemy import func
from sqlalchemy.orm import aliased


class REANAStatus:
    """REANA Status interface."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise REANAStatus class."""
        self.from_ = from_ or (datetime.now() - timedelta(days=1))
        self.until = until or datetime.now()
        self.user = user

    def execute_cmd(self, cmd):
        """Execute a command."""
        return subprocess.check_output(cmd).decode().rstrip("\r\n")

    def get_status(self):
        """Get status summary for REANA."""
        raise NotImplementedError()


class InteractiveSessionsStatus(REANAStatus):
    """Class to retrieve statistics related to REANA interactive sessions."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise InteractiveSessionsStatus class.

        :param from_: From which moment in time to collect information. Not
            implemented yet.
        :param until: Until which moment in time to collect information. Not
            implemented yet.
        :param user: A REANA-DB user model.
        :type from_: datetime
        :type until: datetime
        :type user: reana_db.models.User
        """
        super().__init__(from_=from_, until=until, user=user)

    def get_active(self):
        """Get the number of active interactive sessions."""
        non_active_statuses = [
            RunStatus.stopped,
            RunStatus.deleted,
            RunStatus.failed,
        ]
        active_interactive_sessions = (
            Session.query(InteractiveSession)
            .filter(InteractiveSession.status.notin_(non_active_statuses))
            .count()
        )
        return active_interactive_sessions

    def get_status(self):
        """Get status summary for interactive sessions."""
        return {
            "active": self.get_active(),
        }


class SystemStatus(REANAStatus):
    """Class to retrieve statistics related to the current REANA component."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise SystemStatus class.

        :param from_: From which moment in time to collect information. Not
            implemented yet.
        :param until: Until which moment in time to collect information. Not
            implemented yet.
        :param user: A REANA-DB user model.
        :type from_: datetime
        :type until: datetime
        :type user: reana_db.models.User
        """
        super().__init__(from_=from_, until=until, user=user)

    def uptime(self):
        """Get component uptime."""
        cmd = ["uptime", "-p"]
        return self.execute_cmd(cmd)

    def get_status(self):
        """Get status summary for REANA system."""
        return {
            "uptime": self.uptime(),
        }


class StorageStatus(REANAStatus):
    """Class to retrieve statistics related to REANA storage."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise StorageStatus class.

        :param from_: From which moment in time to collect information. Not
            implemented yet.
        :param until: Until which moment in time to collect information. Not
            implemented yet.
        :param user: A REANA-DB user model.
        :type from_: datetime
        :type until: datetime
        :type user: reana_db.models.User
        """
        super().__init__(from_=from_, until=until, user=user)

    def _get_path(self):
        """Retrieve the path to calculate status from."""
        path = None
        if self.user:
            path = self.user.workspace_path
        else:
            path = SHARED_VOLUME_PATH + "/users"

        return path

    def users_directory_size(self):
        """Get disk usage for users directory."""
        depth = 0
        cmd = ["du", "-h", f"--max-depth={depth}", self._get_path()]
        output = self.execute_cmd(cmd)
        size = output.split()[0]
        return size

    def shared_volume_health(self):
        """REANA shared volume health."""
        cmd = ["df", "-h", SHARED_VOLUME_PATH]
        output = self.execute_cmd(cmd).splitlines()
        headers = output[0].split()
        values = output[1].split()
        used_index = headers.index("Used")
        available_index = headers.index("Avail")
        use_percentage_index = headers.index("Use%")

        return (
            f"{values[used_index]}/{values[available_index]} "
            f"({values[use_percentage_index]})"
        )

    def get_status(self):
        """Get status summary for REANA storage."""
        return {
            "user_directory_size": self.users_directory_size(),
            "shared_volume_health": self.shared_volume_health(),
        }


class UsersStatus(REANAStatus):
    """Class to retrieve statistics related to REANA users."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise UsersStatus class.

        :param from_: From which moment in time to collect information. Not
            implemented yet.
        :param until: Until which moment in time to collect information. Not
            implemented yet.
        :param user: A REANA-DB user model.
        :type from_: datetime
        :type until: datetime
        :type user: reana_db.models.User
        """
        super().__init__(from_=from_, until=until, user=user)

    def active_web_users(self):
        """Get the number of active web users.

        Depends on how long does a session last.
        """
        return Session.query(SessionActivity).count()

    def get_status(self):
        """Get status summary for REANA users."""
        return {
            "active_web_users": self.active_web_users(),
        }


class WorkflowsStatus(REANAStatus):
    """Class to retrieve statistics related to REANA workflows."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise WorkflowsStatus class.

        :param from_: From which moment in time to collect information. Not
            implemented yet.
        :param until: Until which moment in time to collect information. Not
            implemented yet.
        :param user: A REANA-DB user model.
        :type from_: datetime
        :type until: datetime
        :type user: reana_db.models.User
        """
        super().__init__(from_=from_, until=until, user=user)

    def get_workflows_by_status(self, status):
        """Get the number of workflows in status ``status``."""
        number = Session.query(Workflow).filter(Workflow.status == status).count()

        return number

    def restarted_workflows(self):
        """Get the number of restarted workflows."""
        number = Session.query(Workflow).filter(Workflow.restart).count()

        return number

    def stuck_workflows(self):
        """Get the number of stuck workflows."""
        inactivity_threshold = datetime.now() - timedelta(hours=12)
        number = (
            Session.query(Workflow)
            .filter(Workflow.status == RunStatus.running)
            .filter(Workflow.run_started_at <= inactivity_threshold)
            .filter(Workflow.updated <= inactivity_threshold)
            .count()
        )

        return number

    def git_workflows(self):
        """Get the number of Git based workflows."""
        number = Session.query(Workflow).filter(Workflow.git_repo != "").count()

        return number

    def get_status(self):
        """Get status summary for REANA workflows."""
        return {
            "running": self.get_workflows_by_status(RunStatus.running),
            "finished": self.get_workflows_by_status(RunStatus.finished),
            "stuck": self.stuck_workflows(),
            "queued": self.get_workflows_by_status(RunStatus.queued),
            "restarts": self.restarted_workflows(),
            "git_source": self.git_workflows(),
        }


class QuotaUsageStatus(REANAStatus):
    """Class to retrieve statistics related to the current REANA users quota usage."""

    def __init__(self, from_=None, until=None, user=None):
        """Initialise QuotaUsageStatus class.

        :param from_: From which moment in time to collect information. Not
            implemented yet.
        :param until: Until which moment in time to collect information. Not
            implemented yet.
        :param user: A REANA-DB user model.
        :type from_: datetime
        :type until: datetime
        :type user: reana_db.models.User
        """
        super().__init__(from_=from_, until=until, user=user)

    def get_top_five_resource_usage_users(
        self, resource_filter, order, user_resource_filter=True
    ):
        """Query returning top five users according to filter."""
        user_resource_subq = (
            Session.query(UserResource)
            .filter(user_resource_filter)
            .join(UserResource.resource)
            .filter(resource_filter)
            .subquery()
        )
        subq_alias = aliased(UserResource, user_resource_subq)
        return (
            Session.query(User, subq_alias)
            .join(subq_alias, UserResource)
            .group_by(User, UserResource, subq_alias)
            .order_by(order)
            .limit(10)
        )

    def get_top_five_all(self, resource_type):
        """Get the top five users according to quota usage."""
        users = self.get_top_five_resource_usage_users(
            Resource.type_ == resource_type, func.sum(UserResource.quota_used).desc()
        )
        return {
            user.email: {
                "id": str(user.id_),
                "used": ResourceUnit.human_readable_unit(
                    user_resource.resource.unit, user_resource.quota_used
                ),
                "limit": ResourceUnit.human_readable_unit(
                    user_resource.resource.unit, user_resource.quota_limit
                ),
            }
            for user, user_resource in users
        }

    def get_top_five_limited(self, resource_type):
        """Get the top five users with quota limit according to quota usage."""
        users = self.get_top_five_resource_usage_users(
            Resource.type_ == resource_type,
            (
                func.sum(UserResource.quota_used) / func.sum(UserResource.quota_limit)
            ).desc(),
            UserResource.quota_limit != 0,
        )
        return {
            user.email: {
                "id": str(user.id_),
                "used": ResourceUnit.human_readable_unit(
                    user_resource.resource.unit, user_resource.quota_used
                ),
                "limit": ResourceUnit.human_readable_unit(
                    user_resource.resource.unit, user_resource.quota_limit
                ),
            }
            for user, user_resource in users
        }

    def get_status(self):
        """Get status summary for REANA system."""
        return {
            "top_five_all_disk": self.get_top_five_all(ResourceType.disk),
            "top_five_all_cpu": self.get_top_five_all(ResourceType.cpu),
            "top_five_limited_disk": self.get_top_five_limited(ResourceType.disk),
            "top_five_limited_cpu": self.get_top_five_limited(ResourceType.cpu),
        }


STATUS_OBJECT_TYPES = {
    "interactive-sessions": InteractiveSessionsStatus,
    "workflows": WorkflowsStatus,
    "users": UsersStatus,
    "system": SystemStatus,
    "storage": StorageStatus,
    "quota-usage": QuotaUsageStatus,
}
"""High level REANA objects to extract information from."""
