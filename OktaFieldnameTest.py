#!/usr/bin/env python3
"""
This script takes a list of event type strings (examples of raw_event_data.eventType)
and applies a series of mapping rules that mirror the DSL you provided. For each
event type, it returns a dictionary with keys like "event.action", "resource.type", etc.
"""

def process_event_type(event_type):
    result = {"raw_event_data.eventType": event_type}

    # -------------------------
    # Access events
    if event_type.startswith("access"):
        result["resource.type"] = "credential"
        mapping = {
            "access.request.create": "download_resource",
            "access.request.resolve": "create_resource",
            "access.request.settings.update": "request_access",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Analytics events
    elif event_type.startswith("analytics"):
        result["resource.type"] = "report"
        mapping = {
            "analytics.reports.export.download": "download_resource",
            "analytics.reports.export.generate": "create_resource",
            "analytics.reports.export.request": "request_access",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # App events
    elif event_type.startswith("app.access_request"):
        mapping = {
            "app.access_request.approver.approve": "approve_request",
            "app.access_request.approver.deny": "deny_request",
            "app.access_request.delete": "delete_request",
            "app.access_request.deny": "deny_request",
            "app.access_request.expire": "expire_request",
            "app.access_request.grant": "approve_request",
            "app.access_request.request": "request_access",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.ad"):
        mapping = {
            "app.ad.api.user_import.account_locked": "lock_account",
            "app.ad.api.user_import.warn.skipped_contact.attribute_invalid_value": "import_user",
            "app.ad.api.user_import.warn.skipped_user.attribute_invalid_value": "import_user",
            "app.ad.api.user_import.warn.skipped_user.missing_required_attribute": "import_user",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.app_instance"):
        mapping = {
            "app.app_instance.csr.generate": "create_csr",
            "app.app_instance.csr.publish": "publish_csr",
            "app.app_instance.csr.revoke": "revoke_csr",
            "app.app_instance.provision_synchronize_task.completed": "complete_task",
            "app.app_instance.provision_synchronize_task.failed": "execute_task",
            "app.app_instance.provision_synchronize_task.started": "start_task",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.audit_report"):
        result["resource.type"] = "report"
        mapping = {
            "app.audit_report.download.local.active": "download_resource",
            "app.audit_report.download.local.deprov": "download_resource",
            "app.audit_report.download.rogue.report": "download_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.generic"):
        if event_type == "app.generic.unauth_app_access_attempt":
            result["event.action"] = "access_app"
            result["event.outcome"] = "failure"
        else:
            result["event.action"] = "unknown"
        return result

    elif event_type.startswith("app.inbound_del_auth"):
        if event_type == "app.inbound_del_auth.login_success":
            result["event.action"] = "authenticate_user"
        else:
            result["event.action"] = "unknown"
        return result

    elif event_type.startswith("app.kerberos_rich_client"):
        mapping = {
            "app.kerberos_rich_client.account_not_found": "authenticate_user",
            "app.kerberos_rich_client.instance_not_found": "authenticate_user",
            "app.kerberos_rich_client.multiple_accounts_found": "authenticate_user",
            "app.kerberos_rich_client.user_authentication_successful": "authenticate_user",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        if event_type == "app.kerberos_rich_client.multiple_accounts_found":
            result["event.outcome"] = "failure"
        return result

    elif event_type.startswith("app.keys"):
        mapping = {
            "app.keys.clone": "copy_key",
            "app.keys.delete": "delete_key",
            "app.keys.generate": "create_key",
            "app.keys.rotate": "update_key",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.ldap"):
        if event_type == "app.ldap.password.change.failed":
            result["event.action"] = "update_password"
        else:
            result["event.action"] = "unknown"
        return result

    elif event_type.startswith("app.oauth2"):
        mapping = {
            "app.oauth2.admin.consent.grant": "approve_access",
            "app.oauth2.admin.consent.revoke": "revoke_access",
            "app.oauth2.as.authorize": "request_authorization",
            "app.oauth2.as.authorize.code": "request_authorization",
            "app.oauth2.as.authorize.implicit.access_token": "request_token",
            "app.oauth2.as.authorize.implicit.id_token": "request_token",
            "app.oauth2.as.authorize.scope_denied": "deny_request",
            "app.oauth2.as.consent.grant": "approve_access",
            "app.oauth2.as.consent.revoke": "revoke_access",
            "app.oauth2.as.consent.revoke.implicit.as": "revoke_access",
            "app.oauth2.as.consent.revoke.implicit.client": "revoke_access",
            "app.oauth2.as.consent.revoke.implicit.scope": "revoke_access",
            "app.oauth2.as.consent.revoke.implicit.user": "revoke_access",
            "app.oauth2.as.consent.revoke.user": "revoke_access",
            "app.oauth2.as.consent.revoke.user.client": "revoke_access",
            "app.oauth2.as.evaluate.claim": "evaluate_token",
            "app.oauth2.as.key.rollover": "update_key",
            "app.oauth2.as.token.detect_reuse": "evaluate_token",
            "app.oauth2.as.token.grant": "approve_token",
            "app.oauth2.as.token.grant.access_token": "approve_token",
            "app.oauth2.as.token.grant.id_token": "approve_token",
            "app.oauth2.as.token.grant.refresh_token": "update_token",
            "app.oauth2.as.token.revoke": "revoke_token",
            "app.oauth2.token.revoke.implicit.as": "revoke_token",
            "app.oauth2.token.revoke.implicit.client": "revoke_token",
            "app.oauth2.token.revoke.implicit.user": "revoke_token",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        if "app.oauth2.credentials" in event_type:
            result["resource.type"] = "credential"
        if "app.oauth2.invalid_client" in event_type:
            result["event.outcome"] = "failure"
        return result

    elif event_type.startswith("app.office365"):
        # For brevity, only a subset of mappings is provided here.
        mapping = {
            "app.office365.api.change.domain.federation.success": "update_setting",
            "app.office365.api.error.ad.user": "update_user",
            "app.office365.api.error.check.user.exists": "verify_user",
            "app.office365.api.error.create.user": "create_user",
            "app.office365.api.error.deactivate.user": "disable_user",
            # ... (extend with remaining keys as needed)
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        # Additional conditions:
        if "job.complete" in event_type or "sync.complete" in event_type:
            result["event.outcome"] = "success"
        if event_type == "app.office365.license.conversion.job.no.custom.objects.downloaded":
            result["event.outcome"] = "failure"
        if event_type in [
            "app.office365.service.principal.cleanup.job.invalid.credentials",
            "app.office365.service.principal.cleanup.job.skipping.missing.creds",
            "app.office365.service.principal.cleanup.job.skipping.no.service.principal",
            "app.office365.service.principal.cleanup.job.unable.to.delete.service.principal",
        ]:
            result["event.outcome"] = "failure"
        return result

    elif event_type.startswith("app.radius"):
        if event_type in [
            "app.radius.agent.listener.failed",
            "app.radius.agent.listener.succeeded",
            "app.radius.agent.port_inaccessible",
            "app.radius.agent.port_reaccessible",
        ]:
            result["event.action"] = "unknown"
        elif event_type in [
            "app.radius.info_access.no_permission",
            "app.radius.info_access.partial_permission",
        ]:
            result["event.action"] = "access_app"
            result["event.outcome"] = "failure"
        else:
            result["event.action"] = "unknown"
        return result

    elif event_type.startswith("app.realtimesync"):
        result["resource.type"] = "user"
        mapping = {
            "app.realtimesync.import.details.add_user": "add_user",
            "app.realtimesync.import.details.delete_user": "delete_user",
            "app.realtimesync.import.details.update_user": "update_user",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.rum"):
        mapping = {
            "app.rum.config.validation.error": "unknown",
            "app.rum.is.api.account.error": "unknown",
            "app.rum.package.thrown.error": "unknown",
            "app.rum.validation.error": "unknown",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    elif event_type.startswith("app.saml"):
        if event_type == "app.saml.sensitive.attribute.update":
            result["event.action"] = "update_resource"
            result["event.outcome"] = "success"
        else:
            result["event.action"] = "unknown"
        return result

    elif event_type.startswith("app.user_management"):
        mapping = {
            "app.user_management": "import_user",
            "app.user_management.grouppush.mapping.created.from.rule": "update_group",
            "app.user_management.grouppush.mapping.created.from.rule.error.duplicate": "update_group",
            "app.user_management.grouppush.mapping.created.from.rule.error.validation": "update_group",
            "app.user_management.grouppush.mapping.created.from.rule.errors": "update_group",
            "app.user_management.grouppush.mapping.okta.users.ignored": "update_group",
            "app.user_management.import.csv.line.error": "unknown",
            "app.user_management.push_new_user_success": "create_user",
            "app.user_management.update_from_master_failed": "import_user",
            "app.user_management.user_group_import.create_failure": "create_group",
            "app.user_management.user_group_import.delete_success": "delete_group",
            "app.user_management.user_group_import.update_failure": "update_group",
            "app.user_management.user_group_import.upsert_fail": "import_group",
            "app.user_management.user_group_import.upsert_success": "import_group",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        if event_type == "app.user_management.user_group_import.upsert_fail":
            result["event.outcome"] = "failure"
        return result

    # -------------------------
    # Application events
    elif event_type.startswith("application"):
        # application.appuser
        if event_type.startswith("application.appuser"):
            if event_type == "application.appuser.mapping.invalid.expression":
                result["event.action"] = "unknown"
                return result
        # application.cache
        elif event_type.startswith("application.cache"):
            result["resource.type"] = "application"
            if event_type == "application.cache.invalidate":
                result["event.action"] = "update_resource"
            else:
                result["event.action"] = "unknown"
            return result
        # application.configuration
        elif event_type.startswith("application.configuration"):
            mapping = {
                "application.configuration.detect_error": "unknown",
                "application.configuration.disable_delauth_outbound": "update_authentication",
                "application.configuration.disable_fed_broker_mode": "disable_setting",
                "application.configuration.enable_delauth_outbound": "update_authentication",
                "application.configuration.enable_fed_broker_mode": "enable_setting",
                "application.configuration.import_schema": "import_resource",
                "application.configuration.reset_logo": "update_setting",
                "application.configuration.update": "update_setting",
                "application.configuration.update_api_credentials_for_pass_change": "update_password",
                "application.configuration.update_logo": "update_setting",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        # application.integration
        elif event_type.startswith("application.integration"):
            mapping = {
                "application.integration.api_query": "query_api",
                "application.integration.authentication_failure": "authenticate_app",
                "application.integration.general_failure": "unknown",
                "application.integration.rate_limit_exceeded": "alert_api",
                "application.integration.transfer_files": "transfer_owner",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            if event_type == "application.integration.transfer_files":
                result["resource.type"] = "file"
            return result
        # application.lifecycle
        elif event_type.startswith("application.lifecycle"):
            mapping = {
                "application.lifecycle.activate": "enable_app",
                "application.lifecycle.create": "create_app",
                "application.lifecycle.deactivate": "disable_app",
                "application.lifecycle.delete": "delete_app",
                "application.lifecycle.update": "update_app",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        # application.policy
        elif event_type.startswith("application.policy"):
            mapping = {
                "application.policy.sign_on.deny_access": "deny_access",
                "application.policy.sign_on.rule.create": "create_rule",
                "application.policy.sign_on.rule.delete": "delete_rule",
                "application.policy.sign_on.update": "update_rule",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        # application.provision
        elif event_type.startswith("application.provision"):
            mapping = {
                "application.provision.field_mapping_rule.change": "update_rule",
                "application.provision.group.add": "create_group",
                "application.provision.group.import": "import_group",
                "application.provision.group.remove": "delete_group",
                "application.provision.group.update": "update_group",
                "application.provision.group.verify_exists": "verify_group",
                "application.provision.group_membership.add": "add_user",
                "application.provision.group_membership.import": "import_user",
                "application.provision.group_membership.remove": "remove_user",
                "application.provision.group_membership.update": "update_user",
                "application.provision.group_push.activate_mapping": "update_group",
                "application.provision.group_push.delete_appgroup": "delete_group",
                "application.provision.group_push.mapping.and.groups.deleted.rule.deleted": "delete_resource",
                "application.provision.group_push.mapping.app.group.renamed": "update_group",
                "application.provision.group_push.mapping.app.group.renamed.failed": "update_group",
                "application.provision.group_push.mapping.created": "create_resource",
                "application.provision.group_push.mapping.created.from.rule.warning.duplicate.name": "create_resource",
                "application.provision.group_push.mapping.created.from.rule.warning.duplicate.name.tobecreated": "create_resource",
                "application.provision.group_push.mapping.created.from.rule.warning.upsertGroup.duplicate.name": "create_resource",
                "application.provision.group_push.mapping.deactivated.source.group.renamed": "update_resource",
                "application.provision.group_push.mapping.deactivated.source.group.renamed.failed": "update_resource",
                "application.provision.group_push.mapping.update.or.delete.failed": "update_resource",
                "application.provision.group_push.mapping.update.or.delete.failed.with.error": "update_resource",
                "application.provision.group_push.push_memberships": "update_resource",
                "application.provision.group_push.pushed": "create_group",
                "application.provision.group_push.removed": "delete_group",
                "application.provision.group_push.updated": "update_group",
                "application.provision.integration.call_api": "query_api",
                "application.provision.user.activate": "enable_user",
                "application.provision.user.deactivate": "disable_user",
                "application.provision.user.deprovision": "disable_user",
                "application.provision.user.import": "import_user",
                "application.provision.user.import_profile": "import_user",
                "application.provision.user.password": "update_password",
                "application.provision.user.push": "create_user",
                "application.provision.user.push_okta_password": "update_password",
                "application.provision.user.push_password": "update_password",
                "application.provision.user.push_profile": "synchronize_user",
                "application.provision.user.reactivate": "enable_user",
                "application.provision.user.sync": "synchronize_user",
                "application.provision.user.verify_exists": "verify_user",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        # application.registration_policy
        elif event_type.startswith("application.registration_policy"):
            result["resource.type"] = "policy"
            mapping = {
                "application.registration_policy.lifecycle.create": "create_policy",
                "application.registration_policy.lifecycle.update": "update_policy",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        # application.user_membership
        elif event_type.startswith("application.user_membership"):
            mapping = {
                "application.user_membership.add": "add_user",
                "application.user_membership.approve": "approve_user",
                "application.user_membership.change_password": "update_password",
                "application.user_membership.change_username": "update_user",
                "application.user_membership.deprovision": "remove_user",
                "application.user_membership.provision": "add_user",
                "application.user_membership.remove": "remove_user",
                "application.user_membership.restore": "add_user",
                "application.user_membership.restore_password": "reset_password",
                "application.user_membership.revoke": "revoke_user",
                "application.user_membership.show_password": "read_password",
                "application.user_membership.update": "update_user",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

    # -------------------------
    # Certification events
    elif event_type.startswith("certification"):
        result["resource.type"] = "report"
        mapping = {
            "certification.campaign.close": "end_resource",
            "certification.campaign.create": "create_resource",
            "certification.campaign.delete": "delete_resource",
            "certification.campaign.item.decide": "update_resource",
            "certification.campaign.item.remediate": "update_resource",
            "certification.campaign.launch": "execute_resource",
            "certification.campaign.update": "update_resource",
            "certification.remediation.open": "read_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Core events
    elif event_type.startswith("core"):
        mapping = {
            "core.concurrency.org.limit.violation": "alert_api",
            "core.el.evaluate": "unknown",
            "core.user_auth.idp.x509.crl_download_failure": "download_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Credential events
    elif event_type.startswith("credential"):
        result["resource.type"] = "credential"
        mapping = {
            "credential.register": "approve_user",
            "credential.revoke": "revoke_user",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Device events
    elif event_type.startswith("device"):
        result["resource.type"] = "device"
        mapping = {
            "device.enrollment.create": "add_device",
            "device.lifecycle.activate": "enable_device",
            "device.lifecycle.deactivate": "disable_device",
            "device.lifecycle.delete": "remove_device",
            "device.user.add": "add_device",
            "device.user.remove": "remove_device",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Directory events
    elif event_type.startswith("directory"):
        result["resource.type"] = "user"
        mapping = {
            "directory.app_user_profile.bootstrap": "update_user",
            "directory.app_user_profile.update": "update_user",
            "directory.mapping.update": "update_resource",
            "directory.non_default_user_profile.create": "create_user",
            "directory.user_profile.bootstrap": "update_user",
            "directory.user_profile.update": "update_user",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Event hook events
    elif event_type.startswith("event_hook"):
        result["resource.type"] = "destination"
        mapping = {
            "event_hook.activated": "enable_webhook",
            "event_hook.created": "create_webhook",
            "event_hook.deactivated": "disable_webhook",
            "event_hook.deleted": "delete_webhook",
            "event_hook.delivery": "access_webhook",
            "event_hook.updated": "update_webhook",
            "event_hook.verified": "verify_webhook",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Group events
    elif event_type.startswith("group"):
        mapping = {
            "group.application_assignment.add": "add_app",
            "group.application_assignment.remove": "remove_app",
            "group.application_assignment.skip_assignment_reconcile": "unknown",
            "group.application_assignment.update": "update_app",
            "group.lifecycle.create": "create_group",
            "group.lifecycle.delete": "delete_group",
            "group.privilege.grant": "add_permission",
            "group.privilege.revoke": "remove_permission",
            "group.profile.update": "update_group",
            "group.user_membership.add": "add_user",
            "group.user_membership.remove": "remove_user",
            "group.user_membership.rule.add_exclusion": "add_user",
            "group.user_membership.rule.deactivated": "disable_user",
            "group.user_membership.rule.error": "unknown",
            "group.user_membership.rule.evaluation": "read_rule",
            "group.user_membership.rule.invalidate": "disable_rule",
            "group.user_membership.rule.trigger": "execute_rule",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # IAM events
    elif event_type.startswith("iam"):
        mapping = {
            "iam.resourceset.bindings.add": "create_role",
            "iam.resourceset.bindings.delete": "delete_role",
            "iam.resourceset.create": "create_resource",
            "iam.resourceset.delete": "delete_resource",
            "iam.resourceset.resources.add": "add_resource",
            "iam.resourceset.resources.delete": "delete_resource",
            "iam.role.create": "create_role",
            "iam.role.delete": "delete_role",
            "iam.role.permission.conditions.add": "update_permission",
            "iam.role.permission.conditions.delete": "update_permission",
            "iam.role.permissions.add": "add_permission",
            "iam.role.permissions.delete": "delete_permission",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Inline hook events
    elif event_type.startswith("inline_hook"):
        result["resource.type"] = "destination"
        mapping = {
            "inline_hook.activated": "enable_webhook",
            "inline_hook.created": "create_webhook",
            "inline_hook.deactivated": "disable_webhook",
            "inline_hook.deleted": "delete_webhook",
            "inline_hook.executed": "access_webhook",
            "inline_hook.response.processed": "access_webhook",
            "inline_hook.updated": "update_webhook",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Master application events
    elif event_type.startswith("master_application"):
        if event_type == "master_application.user_membership.add":
            result["event.action"] = "add_user"
        else:
            result["event.action"] = "unknown"
        return result

    # -------------------------
    # MIM events
    elif event_type.startswith("mim"):
        mapping = {
            "mim.command.generic.acknowledged": "unknown",
            "mim.command.generic.cancelled": "unknown",
            "mim.command.generic.delegated": "unknown",
            "mim.command.generic.error": "unknown",
            "mim.command.generic.new": "unknown",
            "mim.command.generic.notnow": "unknown",
            "mim.command.ios.acknowledged": "unknown",
            "mim.command.ios.cancelled": "unknown",
            "mim.command.ios.error": "unknown",
            "mim.command.ios.formaterror": "unknown",
            "mim.command.ios.new": "unknown",
            "mim.createEnrollment.ANDROID": "add_device",
            "mim.createEnrollment.IOS": "add_device",
            "mim.createEnrollment.OSX": "add_device",
            "mim.createEnrollment.UNKNOWN": "add_device",
            "mim.createEnrollment.WINDOWS": "add_device",
            "mim.streamDevicesAppListCSVDownload": "download_resource",
            "mim.streamDevicesCSVDownload": "download_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Network zone events
    elif event_type.startswith("network_zone"):
        if event_type == "network_zone.rule.disabled":
            result["event.action"] = "disable_rule"
        else:
            result["event.action"] = "unknown"
        return result

    # -------------------------
    # OAuth2 events
    elif event_type.startswith("oauth2"):
        mapping = {
            "oauth2.as.activated": "enable_resource",
            "oauth2.as.created": "create_resource",
            "oauth2.as.deactivated": "disable_resource",
            "oauth2.as.deleted": "delete_resource",
            "oauth2.as.updated": "update_resource",
            "oauth2.claim.created": "create_resource",
            "oauth2.claim.deleted": "delete_resource",
            "oauth2.claim.updated": "update_resource",
            "oauth2.scope.created": "create_resource",
            "oauth2.scope.deleted": "delete_resource",
            "oauth2.scope.updated": "update_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # OMM events
    elif event_type.startswith("omm"):
        mapping = {
            "omm.app.VPN.settings.changed": "update_setting",
            "omm.app.WIFI.settings.changed": "update_setting",
            "omm.app.eas.cert_based.settings.changed": "update_setting",
            "omm.app.eas.disabled": "update_setting",
            "omm.app.eas.settings.changed": "update_setting",
            "omm.cma.created": "create_resource",
            "omm.cma.deleted": "delete_resource",
            "omm.cma.updated": "update_resource",
            "omm.enrollment.changed": "update_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Org events
    elif event_type.startswith("org"):
        if event_type == "org.not_configured_origin.redirection.usage":
            result["event.action"] = "unknown"
        else:
            result["event.action"] = "unknown"
        return result

    # -------------------------
    # PKI events
    elif event_type.startswith("pki"):
        mapping = {
            "pki.cert.issue": "issue_certificate",
            "pki.cert.renew": "update_certificate",
            "pki.cert.revoke": "revoke_certificate",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Plugin events
    elif event_type.startswith("plugin"):
        mapping = {
            "plugin.downloaded": "download_resource",
            "plugin.script_status": "update_status",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Policy events
    elif event_type.startswith("policy"):
        if event_type.startswith("policy.evaluate_sign_on"):
            if event_type == "policy.evaluate_sign_on":
                result["event.action"] = "evaluate_policy"
            else:
                result["event.action"] = "unknown"
            return result
        elif event_type.startswith("policy.execute"):
            if event_type == "policy.execute.user.start":
                result["event.action"] = "add_policy"
            else:
                result["event.action"] = "unknown"
            return result
        elif event_type.startswith("policy.lifecycle"):
            result["resource.type"] = "policy"
            mapping = {
                "policy.lifecycle.activate": "enable_policy",
                "policy.lifecycle.create": "create_policy",
                "policy.lifecycle.deactivate": "disable_policy",
                "policy.lifecycle.delete": "delete_policy",
                "policy.lifecycle.overwrite": "update_policy",
                "policy.lifecycle.update": "update_policy",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        elif event_type.startswith("policy.rule"):
            result["resource.type"] = "rule"
            mapping = {
                "policy.rule.action.execute": "execute_rule",
                "policy.rule.activate": "enable_rule",
                "policy.rule.add": "add_rule",
                "policy.rule.deactivate": "disable_rule",
                "policy.rule.delete": "delete_rule",
                "policy.rule.invalidate": "disable_rule",
                "policy.rule.update": "update_rule",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        elif event_type.startswith("policy.scheduled"):
            if event_type == "policy.scheduled.execute":
                result["event.action"] = "execute_policy"
            else:
                result["event.action"] = "unknown"
            return result

    # -------------------------
    # Scheduled action events
    elif event_type.startswith("scheduled_action"):
        mapping = {
            "scheduled_action.user_suspension.canceled": "delete_task",
            "scheduled_action.user_suspension.completed": "complete_task",
            "scheduled_action.user_suspension.scheduled": "create_task",
            "scheduled_action.user_suspension.updated": "update_task",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Security events
    elif event_type.startswith("security"):
        mapping = {
            "security.authenticator.lifecycle.activate": "enable_app",
            "security.authenticator.lifecycle.create": "create_app",
            "security.authenticator.lifecycle.deactivate": "disable_app",
            "security.authenticator.lifecycle.update": "update_app",
            "security.behavior.settings.create": "create_setting",
            "security.behavior.settings.delete": "delete_setting",
            "security.behavior.settings.update": "update_setting",
            "security.device.add_request_blacklist_policy": "add_policy",
            "security.device.remove_request_blacklist_policy": "remove_policy",
            "security.device.temporarily_disable_blacklisting": "disable_policy",
            "security.request.blocked": "deny_request",
            "security.session.detect_client_roaming": "unknown",  # or "alert_user" per second occurrence
            "security.threat.configuration.update": "update_setting",
            "security.threat.detected": "alert_resource",
            "security.voice.add_country_blacklist": "add_rule",
            "security.voice.remove_country_blacklist": "remove_rule",
            "security.zone.make_blacklist": "create_rule",
            "security.zone.remove_blacklist": "remove_rule",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Self service events
    elif event_type.startswith("self_service"):
        mapping = {
            "self_service.disabled": "disable_resource",
            "self_service.enabled": "enable_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # System events (many subcategories)
    elif event_type.startswith("system"):
        if event_type.startswith("system.agent"):
            mapping = {
                "system.agent.ad.connect": "connect_app",
                "system.agent.ad.create": "create_app",
                "system.agent.ad.deactivate": "disable_app",
                "system.agent.ad.delete": "delete_app",
                "system.agent.ad.import_ou": "import_resource",
                "system.agent.ad.import_user": "import_user",
                "system.agent.ad.invoke_dir": "execute_command",
                "system.agent.ad.reactivate": "enable_app",
                "system.agent.ad.read_config": "read_config",
                "system.agent.ad.read_dirsync": "read_resource",
                "system.agent.ad.read_ldap": "read_resource",
                "system.agent.ad.read_schema": "read_schema",
                "system.agent.ad.read_topology": "read_resource",
                "system.agent.ad.realtimesync": "synchronize_user",
                "system.agent.ad.reset_user_password": "update_password",
                "system.agent.ad.start": "execute_app",
                "system.agent.ad.unlock_user_account": "unlock_user",
                "system.agent.ad.update": "update_app",
                "system.agent.ad.update_user": "update_user",
                "system.agent.ad.upgrade": "upgrade_app",
                "system.agent.ad.upload_iwa_log": "upload_resource",
                "system.agent.ad.upload_log": "upload_resource",
                "system.agent.ad.write_ldap": "update_resource",
                "system.agent.connector.connect": "connect_app",
                "system.agent.connector.deactivate": "disable_app",
                "system.agent.connector.delete": "delete_app",
                "system.agent.connector.reactivate": "enable_app",
                "system.agent.ldap.change_user_password": "update_password",
                "system.agent.ldap.create_user_JIT": "create_user",
                "system.agent.ldap.disconnect": "disconnect_app",
                "system.agent.ldap.realtimesync": "synchronize_user",
                "system.agent.ldap.reconnect": "connect_app",
                "system.agent.ldap.reset_user_password": "update_password",
                "system.agent.ldap.unlock_user_account": "unlock_user",
                "system.agent.ldap.update_user_password": "update_password",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            if "system.agent.ad" in event_type:
                result["resource.type"] = "application"
                result["application.name"] = "AD agent"
            if "system.agent.ldap" in event_type:
                result["resource.type"] = "application"
                result["application.name"] = "LDAP agent"
            if event_type == "system.agent.connector.connect":
                result["resource.type"] = "application"
            return result

        elif event_type.startswith("system.api_token"):
            mapping = {
                "system.api_token.create": "create_token",
                "system.api_token.enable": "approve_token",
                "system.api_token.revoke": "revoke_token",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.billing"):
            if event_type == "system.billing.sms_usage_sent":
                result["event.action"] = "synchronize_resource"
                result["resource.type"] = "report"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.client"):
            if event_type in ["system.client.concurrency_rate_limit.violation", "system.client.rate_limit.violation"]:
                result["event.action"] = "alert_api"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.csv"):
            if event_type == "system.csv.import_user":
                result["event.action"] = "import_user"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.directory"):
            mapping = {
                "system.directory.debugger.extend": "execute_app",
                "system.directory.debugger.grant": "approve_app",
                "system.directory.debugger.query_executed": "execute_app",
                "system.directory.debugger.revoke": "revoke_app",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.email"):
            mapping = {
                "system.email.account_unlock.sent_message": "notify_mfa",
                "system.email.challenge_factor_redeemed": "notify_issue",
                "system.email.delivery": "notify_issue",
                "system.email.mfa_enroll_notification.sent_message": "notify_mfa",
                "system.email.mfa_reset_notification.sent_message": "notify_mfa",
                "system.email.new_device_notification.sent_message": "notify_mfa",
                "system.email.password_reset.sent_message": "notify_mfa",
                "system.email.send_factor_verify_message": "notify_mfa",
                "system.email.template.update": "notify_issue",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.feature"):
            if event_type == "system.feature.ea_auto_enroll":
                result["event.action"] = "update_organization"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.idp"):
            result["resource.type"] = "application"
            mapping = {
                "system.idp.lifecycle.create": "create_resource",
                "system.idp.lifecycle.deactivate": "disable_resource",
                "system.idp.lifecycle.delete": "delete_resource",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.import"):
            mapping = {
                "system.import.clear.unconfirmed.users.summary": "remove_resource",
                "system.import.complete": "import_resource",
                "system.import.complete_batch": "import_resource",
                "system.import.custom_object.complete": "import_resource",
                "system.import.custom_object.create": "create_resource",
                "system.import.custom_object.delete": "delete_resource",
                "system.import.custom_object.update": "update_resource",
                "system.import.download.complete": "import_resource",
                "system.import.download.start": "import_resource",
                "system.import.group.complete": "import_group",
                "system.import.group.create": "create_group",
                "system.import.group.delete": "delete_group",
                "system.import.group.start": "import_resource",
                "system.import.group.update": "update_group",
                "system.import.group_membership.complete": "import_resource",
                "system.import.implicit_deletion.complete": "delete_resource",
                "system.import.implicit_deletion.start": "delete_resource",
                "system.import.import_profile": "import_user",
                "system.import.import_provisioning_info": "import_resource",
                "system.import.membership_processing.complete": "import_resource",
                "system.import.membership_processing.start": "import_resource",
                "system.import.object_creation.complete": "create_resource",
                "system.import.object_creation.start": "create_resource",
                "system.import.roadblock": "import_resource",
                "system.import.roadblock.reschedule_and_resume": "import_resource",
                "system.import.roadblock.resume": "import_resource",
                "system.import.roadblock.updated": "update_resource",
                "system.import.start": "import_resource",
                "system.import.user.complete": "import_user",
                "system.import.user.create": "create_user",
                "system.import.user.delete": "delete_user",
                "system.import.user.match": "unknown",
                "system.import.user.start": "import_user",
                "system.import.user.suspend": "disable_user",
                "system.import.user.unsuspend": "enable_user",
                "system.import.user.unsuspend_after_confirm": "enable_user",
                "system.import.user.update": "update_user",
                "system.import.user.update_user_lifecycle_from_master": "update_user",
                "system.import.user_csv.complete": "import_user",
                "system.import.user_csv.start": "import_user",
                "system.import.user_matching.complete": "verify_user",
                "system.import.user_matching.start": "verify_user",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.iwa"):
            mapping = {
                "system.iwa.create": "create_resource",
                "system.iwa.go_offline": "unknown",
                "system.iwa.go_online": "unknown",
                "system.iwa.promote_primary": "unknown",
                "system.iwa.remove": "delete_resource",
                "system.iwa.update": "update_resource",
                "system.iwa.use_default": "unknown",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.iwa_agentless"):
            mapping = {
                "system.iwa_agentless.auth": "authenticate_user",
                "system.iwa_agentless.redirect": "authenticate_user",
                "system.iwa_agentless.update": "update_resource",
                "system.iwa_agentless.not_found": "authenticate_user",
                "system.iwa_agentless.user.not_found": "authenticate_user",
                "system.iwa_agentless_kerberos.update": "update_resource",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.ldapi"):
            if event_type == "system.ldapi.bind":
                result["event.action"] = "unknown"
            elif event_type == "system.ldapi.search":
                result["event.action"] = "read_resource"
            elif event_type == "system.ldapi.unbind":
                result["event.action"] = "unknown"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.mfa"):
            if event_type == "system.mfa.factor.activate":
                result["event.action"] = "enable_mfa"
            elif event_type == "system.mfa.factor.deactivate":
                result["event.action"] = "disable_mfa"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.org"):
            mapping = {
                "system.org.lifecycle.create": "create_organization",
                "system.org.rate_limit.expiration.warning": "alert_api",
                "system.org.rate_limit.violation": "alert_api",
                "system.org.rate_limit.warning": "alert_api",
                "system.org.task.remove": "delete_resource",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.push"):
            if event_type == "system.push.send_factor_verify_push":
                result["event.action"] = "notify_mfa"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("system.sms"):
            mapping = {
                "system.sms.receive_status": "update_status",
                "system.sms.send_account_unlock_message": "unlock_user",
                "system.sms.send_factor_verify_message": "notify_mfa",
                "system.sms.send_okta_push_verify_message": "notify_mfa",
                "system.sms.send_password_reset_message": "reset_password",
                "system.sms.send_phone_verification_message": "notify_mfa",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("system.voice"):
            mapping = {
                "system.voice.receive_status": "update_status",
                "system.voice.send_account_unlock_call": "unlock_user",
                "system.voice.send_call": "notify_mfa",
                "system.voice.send_mfa_challenge_call": "notify_mfa",
                "system.voice.send_password_reset_call": "reset_password",
                "system.voice.send_phone_verification_call": "notify_mfa",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        else:
            result["event.action"] = "unknown"
            return result

    # -------------------------
    # Task events
    elif event_type.startswith("task"):
        result["resource.type"] = "task"
        mapping = {
            "task.lifecycle.activate": "enable_resource",
            "task.lifecycle.create": "create_resource",
            "task.lifecycle.deactivate": "disable_resource",
            "task.lifecycle.delete": "delete_resource",
            "task.lifecycle.update": "update_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # User events
    elif event_type.startswith("user"):
        if event_type.startswith("user.account"):
            mapping = {
                "user.account.access_super_user_app": "access_app",
                "user.account.lock": "lock_user",
                "user.account.lock.limit": "lock_user",
                "user.account.privilege.grant": "add_permission",
                "user.account.privilege.revoke": "remove_permission",
                "user.account.report_suspicious_activity_by_enduser": "alert_user",
                "user.account.reset_password": "update_password",
                "user.account.unlock": "unlock_user",
                "user.account.unlock_by_admin": "unlock_user",
                "user.account.unlock_failure": "unlock_user",
                "user.account.unlock_token": "unlock_token",
                "user.account.update_password": "update_password",
                "user.account.update_primary_email": "update_user",
                "user.account.update_profile": "update_user",
                "user.account.update_secondary_email": "update_user",
                "user.account.update_user_type": "update_role",
                "user.account.use_token": "evaluate_token",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("user.authentication"):
            mapping = {
                "user.authentication.auth": "authenticate_user",
                "user.authentication.auth_via_AD_app": "authenticate_user",
                "user.authentication.auth_via_AD_agent": "authenticate_user",
                "user.authentication.auth_via_IDP": "authenticate_user",
                "user.authentication.auth_via_LDAP_agent": "authenticate_user",
                "user.authentication.auth_via_LDAP_app": "authenticate_user",
                "user.authentication.auth_via_inbound_SAML": "authenticate_user",
                "user.authentication.auth_via_inbound_delauth": "authenticate_user",
                "user.authentication.auth_via_iwa": "authenticate_user",
                "user.authentication.auth_via_mfa": "verify_user",
                "user.authentication.auth_via_radius": "authenticate_user",
                "user.authentication.auth_via_richclient": "authenticate_user",
                "user.authentication.auth_via_social": "authenticate_user",
                "user.authentication.authenticate": "authenticate_user",
                "user.authentication.slo": "logout_user",
                "user.authentication.sso": "access_app",
                "user.authentication.verify": "verify_user",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("user.credential"):
            if event_type == "user.credential.enroll":
                result["event.action"] = "enroll_certificate"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("user.import"):
            if event_type == "user.import.password":
                result["event.action"] = "update_password"
            else:
                result["event.action"] = "unknown"
            return result

        elif event_type.startswith("user.lifecycle"):
            mapping = {
                "user.lifecycle.activate": "enable_user",
                "user.lifecycle.create": "create_user",
                "user.lifecycle.deactivate": "disable_user",
                "user.lifecycle.delete.completed": "delete_user",
                "user.lifecycle.delete.initiated": "delete_user",
                "user.lifecycle.jit.error.read_only": "create_user",
                "user.lifecycle.password_mass_expiry": "expire_password",
                "user.lifecycle.reactivate": "enable_user",
                "user.lifecycle.suspend": "lock_user",
                "user.lifecycle.unsuspend": "unlock_user",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result

        elif event_type.startswith("user.mfa"):
            mapping = {
                "user.mfa.attempt_bypass": "alert_mfa",
                "user.mfa.factor.activate": "add_mfa",
                "user.mfa.factor.deactivate": "remove_mfa",
                "user.mfa.factor.reset_all": "remove_mfa",
                "user.mfa.factor.update": "change_mfa",
                "user.mfa.okta_verify": "verify_mfa",
                "user.mfa.okta_verify.deny_push": "verify_mfa",
                "user.mfa.okta_verify.deny_push_upgrade_needed": "verify_mfa",
                "user.mfa.factor.suspend": "remove_mfa",
                "user.mfa.factor.unsuspend": "add_mfa",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            if "user.mfa.okta_verify.deny_push" in event_type:
                result["event.outcome"] = "failure"
            return result

        elif event_type.startswith("user.session"):
            mapping = {
                "user.session.access_admin_app": "access_app",
                "user.session.clear": "end_session",
                "user.session.end": "logout_user",
                "user.session.expire": "expire_session",
                "user.session.impersonation.end": "impersonate_user",
                "user.session.impersonation.extend": "impersonate_user",
                "user.session.impersonation.grant": "approve_access",
                "user.session.impersonation.initiate": "impersonate_user",
                "user.session.impersonation.revoke": "revoke_access",
                "user.session.start": "login_user",
            }
            result["event.action"] = mapping.get(event_type, "unknown")
            return result
        else:
            result["event.action"] = "unknown"
            return result

    # -------------------------
    # Workflows events
    elif event_type.startswith("workflows"):
        mapping = {
            "workflows.user.connection.create": "create_workflow",
            "workflows.user.connection.delete": "delete_workflow",
            "workflows.user.connection.reauthorize": "update_workflow",
            "workflows.user.connection.revoke": "disable_workflow",
            "workflows.user.delegatedflow.run": "execute_workflow",
            "workflows.user.flow.activate": "enable_workflow",
            "workflows.user.flow.create": "create_workflow",
            "workflows.user.flow.deactivate": "disable_workflow",
            "workflows.user.flow.delete": "delete_workflow",
            "workflows.user.flow.execution.cancel": "cancel_workflow",
            "workflows.user.flow.export": "download_resource",
            "workflows.user.flow.import": "import_resource",
            "workflows.user.flow.save": "update_workflow",
            "workflows.user.folder.create": "create_resource",
            "workflows.user.folder.delete": "delete_resource",
            "workflows.user.folder.export": "download_resource",
            "workflows.user.folder.import": "import_resource",
            "workflows.user.folder.rename": "update_resource",
            "workflows.user.table.create": "create_resource",
            "workflows.user.table.delete": "delete_resource",
            "workflows.user.table.export": "download_resource",
            "workflows.user.table.import": "import_resource",
            "workflows.user.table.schema.export": "download_resource",
            "workflows.user.table.schema.import": "import_resource",
            "workflows.user.table.update": "update_resource",
            "workflows.user.table.view": "read_resource",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        if event_type.startswith("workflows.user.folder"):
            result["resource.type"] = "folder"
        elif event_type.startswith("workflows.user.table"):
            result["resource.type"] = "table"
        return result

    # -------------------------
    # Zone events
    elif event_type.startswith("zone"):
        mapping = {
            "zone.activate": "enable_rule",
            "zone.create": "create_rule",
            "zone.deactivate": "disable_rule",
            "zone.delete": "delete_rule",
            "zone.make_blacklist": "create_rule",
            "zone.remove_blacklist": "remove_rule",
            "zone.update": "update_rule",
        }
        result["event.action"] = mapping.get(event_type, "unknown")
        return result

    # -------------------------
    # Fallback
    result["event.action"] = "unknown"
    return result

def process_event_types(event_types):
    return [process_event_type(et) for et in event_types]

def main():
    # Example list of event type strings
    event_types = [
        "access.request.create",
        "analytics.reports.export.download",
        "app.access_request.approver.approve",
        "app.ldap.password.change.failed",
        "app.kerberos_rich_client.multiple_accounts_found",
        "app.oauth2.as.token.grant.refresh_token",
        "user.session.start",
        "system.agent.ad.connect",
        "zone.activate",
        "unknown.event.type"
    ]
    processed = process_event_types(event_types)
    for event in processed:
        print(event)

if __name__ == "__main__":
    main()
