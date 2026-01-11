#!/usr/bin/env python3
"""
Azure Authentication Module

Handles Service Principal authentication for Azure services.
Uses environment variables for credentials.
"""

import os
import sys
from azure.identity import ClientSecretCredential
from azure.mgmt.apimanagement import ApiManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from msal import ConfidentialClientApplication

from exceptions import AzureAuthError


def get_credentials():
    """
    Get Azure Service Principal credentials from environment variables.
    
    Returns:
        ClientSecretCredential: Authenticated credential object
        
    Raises:
        AzureAuthError: If required environment variables are missing
    """
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    tenant_id = os.getenv('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        missing = []
        if not client_id:
            missing.append('AZURE_CLIENT_ID')
        if not client_secret:
            missing.append('AZURE_CLIENT_SECRET')
        if not tenant_id:
            missing.append('AZURE_TENANT_ID')
        raise AzureAuthError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    
    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        return credential
    except Exception as e:
        raise AzureAuthError(f"Failed to create credentials: {str(e)}")


def get_subscription_id():
    """
    Get Azure subscription ID from environment variable.
    
    Returns:
        str: Subscription ID
        
    Raises:
        AzureAuthError: If AZURE_SUBSCRIPTION_ID is not set
    """
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    if not subscription_id:
        raise AzureAuthError("AZURE_SUBSCRIPTION_ID environment variable is not set")
    return subscription_id

def get_storage_management_client():
    """
    Get authenticated Storage Management client.
    
    Returns:
        StorageManagementClient: Authenticated storage management client
        
    Raises:
        AzureAuthError: If authentication fails
    """
    try:
        credential = get_credentials()
        subscription_id = get_subscription_id()
        return StorageManagementClient(credential, subscription_id)
    except AzureAuthError:
        raise
    except Exception as e:
        raise AzureAuthError(f"Failed to create Storage Management client: {str(e)}")


def get_blob_service_client(storage_account_name, use_managed_identity=False):
    """
    Get authenticated Blob Service client.
    
    Args:
        storage_account_name: Name of the storage account
        use_managed_identity: If True, use managed identity (default: False, use Service Principal)
    
    Returns:
        BlobServiceClient: Authenticated blob service client
        
    Raises:
        AzureAuthError: If authentication fails
    """
    try:
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        if use_managed_identity:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
        else:
            credential = get_credentials()
        
        return BlobServiceClient(account_url=account_url, credential=credential)
    except AzureAuthError:
        raise
    except Exception as e:
        raise AzureAuthError(f"Failed to create Blob Service client: {str(e)}")


def get_table_service_client(storage_account_name, use_managed_identity=False):
    """
    Get authenticated Table Service client.
    
    Args:
        storage_account_name: Name of the storage account
        use_managed_identity: If True, use managed identity (default: False, use Service Principal)
    
    Returns:
        TableServiceClient: Authenticated table service client
        
    Raises:
        AzureAuthError: If authentication fails
    """
    try:
        account_url = f"https://{storage_account_name}.table.core.windows.net"
        
        if use_managed_identity:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
        else:
            credential = get_credentials()
        
        return TableServiceClient(endpoint=account_url, credential=credential)
    except AzureAuthError:
        raise
    except Exception as e:
        raise AzureAuthError(f"Failed to create Table Service client: {str(e)}")

def get_graph_client():
    """
    Get authenticated Microsoft Graph API client (MSAL).
    
    Returns:
        ConfidentialClientApplication: Authenticated MSAL application client
        
    Raises:
        AzureAuthError: If authentication fails
    """
    try:
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        tenant_id = os.getenv('AZURE_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            raise AzureAuthError("Missing required environment variables for Graph API")
        
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        
        app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority
        )
        
        return app
    except AzureAuthError:
        raise
    except Exception as e:
        raise AzureAuthError(f"Failed to create Graph API client: {str(e)}")


def get_graph_token():
    """
    Get access token for Microsoft Graph API.
    
    Returns:
        str: Access token
        
    Raises:
        AzureAuthError: If token acquisition fails
    """
    try:
        app = get_graph_client()
        scopes = ["https://graph.microsoft.com/.default"]
        
        result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise AzureAuthError(f"Failed to acquire token: {error}")
        
        return result["access_token"]
    except AzureAuthError:
        raise
    except Exception as e:
        raise AzureAuthError(f"Failed to get Graph API token: {str(e)}")

