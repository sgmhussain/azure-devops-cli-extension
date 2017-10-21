# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------


import dateutil.parser
import dateutil.tz

from vsts.cli.common.identities import (ensure_display_names_in_cache,
                                        get_display_name_from_identity_id,
                                        get_identities)
from vsts.cli.common.vsts import get_first_vss_instance_uri
from collections import OrderedDict

_pr_title_truncation_length = 50
_work_item_title_truncation_length = 70


def transform_pull_requests_table_output(result):
    table_output = []
    for item in result:
        table_output.append(_transform_pull_request_row(item))
    return table_output


def transform_pull_request_table_output(result):
    table_output = [_transform_pull_request_row(result)]
    return table_output


def _transform_pull_request_row(row):
    table_row = OrderedDict()
    table_row['ID'] = row['pullRequestId']
    table_row['Created'] = dateutil.parser.parse(row['creationDate']).astimezone(dateutil.tz.tzlocal()).date()
    table_row['Creator'] = row['createdBy']['uniqueName']
    title = row['title']
    if len(title) > _pr_title_truncation_length:
        title = title[0:_pr_title_truncation_length - 3] + '...'
    table_row['Title'] = title
    table_row['Status'] = row['status'].capitalize()
    table_row['Repository'] = row['repository']['name']
    return table_row


def transform_reviewers_table_output(result):
    table_output = []
    for item in sorted(result, key=_get_reviewer_table_key):
        table_output.append(_transform_reviewer_row(item))
    return table_output


def transform_reviewer_table_output(result):
    table_output = [_transform_reviewer_row(result)]
    return table_output


def _get_reviewer_table_key(row):
    if row['isRequired']:
        key = '0'
    else:
        key = '1'
    key += row['displayName']
    return key


_unique_name_group_prefix = 'vstfs:///'


def _transform_reviewer_row(row):
    table_row = OrderedDict()
    table_row['Name'] = row['displayName']
    if row['uniqueName'][0:len(_unique_name_group_prefix)] != _unique_name_group_prefix:
        table_row['Email'] = row['uniqueName']
    else:
        table_row['Email'] = ' '
    table_row['ID'] = row['id']
    table_row['Vote'] = _get_vote_from_vote_number(int(row['vote']))
    if row['isRequired']:
        table_row['Required'] = 'True'
    else:
        table_row['Required'] = 'False'
    return table_row


def transform_work_items_table_output(result):
    table_output = []
    for item in result:
        table_output.append(_transform_work_items_row(item))
    return table_output


def transform_work_item_table_output(result):
    table_output = [_transform_work_items_row(result)]
    return table_output


def _transform_work_items_row(row):
    table_row = OrderedDict()
    table_row['ID'] = row['id']
    if 'fields' in row:
        if 'System.WorkItemType' in row['fields']:
            table_row['Type'] = row['fields']['System.WorkItemType']
        else:
            table_row['Type'] = ' '
        if 'System.AssignedTo' in row['fields']:
            table_row['Assigned To'] = row['fields']['System.AssignedTo']
        else:
            table_row['Assigned To'] = ' '
        if 'System.State' in row['fields']:
            table_row['State'] = row['fields']['System.State']
        else:
            table_row['State'] = ' '
        if 'System.Title' in row['fields']:
            title = row['fields']['System.Title']
            if len(title) > _work_item_title_truncation_length:
                title = title[0:_work_item_title_truncation_length - 3] + '...'
            table_row['Title'] = title
        else:
            table_row['Title'] = ' '
    else:
        table_row['Assigned To'] = ' '
        table_row['State'] = ' '
        table_row['Title'] = ' '
    return table_row


def _get_vote_from_vote_number(number):
    if number == 10:
        return 'Approved'
    elif number == 5:
        return 'Approved with suggestions'
    elif number == -5:
        return 'Waiting for author'
    elif number == -10:
        return 'Rejected'
    else:
        return ' '


def transform_policies_table_output(result):
    table_output = []
    reviewer_ids = []
    for item in result:
        reviewer_id = get_required_reviewer_from_evaluation_row(item)
        if reviewer_id is not None:
            reviewer_ids.append(get_required_reviewer_from_evaluation_row(item))
    team_instance = get_first_vss_instance_uri()
    ensure_display_names_in_cache(team_instance, reviewer_ids)
    for item in result:
        reviewer_id = get_required_reviewer_from_evaluation_row(item)
        if reviewer_id is not None:
            display_name = get_display_name_from_identity_id(team_instance, reviewer_id)
        else:
            display_name = None
        if display_name is not None:
            table_output.append(_transform_policy_row(item, display_name))
        else:
            table_output.append(_transform_policy_row(item))
    return sorted(table_output, key=_get_policy_table_key)


def get_required_reviewer_from_evaluation_row(row):
    if 'requiredReviewerIds' in row['configuration']['settings'] and len(
            row['configuration']['settings']['requiredReviewerIds']) == 1:
        return row['configuration']['settings']['requiredReviewerIds'][0]
    else:
        return None


def transform_policy_table_output(result):
    table_output = [_transform_policy_row(result)]
    return table_output


def _get_policy_table_key(row):
    if row['Blocking'] == 'True':
        key = '0'
    else:
        key = '1'
    key += row['Policy']
    return key


def _transform_policy_row(row, identity_display_name=None):
    table_row = OrderedDict()
    table_row['Evaluation ID'] = row['evaluationId']
    table_row['Policy'] = _build_policy_name(row, identity_display_name)
    if row['configuration']['isBlocking']:
        table_row['Blocking'] = 'True'
    else:
        table_row['Blocking'] = 'False'
    table_row['Status'] = _convert_policy_status(row['status'])
    if row['context'] and 'isExpired' in row['context']:
        if row['context']['isExpired']:
            table_row['Expired'] = 'True'
        else:
            table_row['Expired'] = 'False'
    else:
        # Not Applicable
        table_row['Expired'] = ' '
    if row['context'] and 'buildId' in row['context'] and row['context']['buildId'] is not None:
        table_row['Build ID'] = row['context']['buildId']
    else:
        table_row['Build ID'] = ' '
    return table_row


def _build_policy_name(row, identity_display_name=None):
    policy = row['configuration']['type']['displayName']
    if 'displayName' in row['configuration']['settings']\
            and row['configuration']['settings']['displayName'] is not None:
        policy += ' (' + row['configuration']['settings']['displayName'] + ')'
    if 'minimumApproverCount' in row['configuration']['settings']\
            and row['configuration']['settings']['minimumApproverCount'] is not None:
        policy += ' (' + str(row['configuration']['settings']['minimumApproverCount']) + ')'
    if identity_display_name is not None and 'requiredReviewerIds' in row['configuration']['settings']:
        if len(row['configuration']['settings']['requiredReviewerIds']) > 1:
            policy += ' (' + str(len(row['configuration']['settings']['requiredReviewerIds'])) + ')'
        elif len(row['configuration']['settings']['requiredReviewerIds']) == 1:
            policy += ' (' + identity_display_name + ')'
    return policy


def _convert_policy_status(status):
    if status == 'queued':
        return ' '
    else:
        return status.capitalize()