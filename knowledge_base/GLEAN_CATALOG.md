# Glean Solution Catalog

## Overview

This catalog defines Glean's native connector ecosystem, implementation tiers, and integration requirements. Reference this document when mapping customer needs to available solutions.

---

## Native Connector Categories

### Knowledge Management
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Confluence | Native | Standard |
| SharePoint | Native | Standard |
| Notion | Native | Standard |
| Google Drive | Native | Standard |
| Dropbox | Native | Standard |
| Box | Native | Standard |
| OneDrive | Native | Standard |
| Coda | Native | Standard |
| Guru | Native | Standard |
| Tettra | Native | Standard |
| Slab | Native | Standard |
| GitBook | Native | Standard |

### Communication & Collaboration
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Slack | Native | Standard |
| Microsoft Teams | Native | Standard |
| Zoom | Native | Standard |
| Google Chat | Native | Standard |
| Discord | Native | Configuration |
| Webex | Native | Standard |

### Engineering & Development
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| GitHub | Native | Standard |
| GitLab | Native | Standard |
| Bitbucket | Native | Standard |
| Jira | Native | Standard |
| Linear | Native | Standard |
| Asana | Native | Standard |
| Monday.com | Native | Standard |
| Trello | Native | Standard |
| Azure DevOps | Native | Standard |
| Shortcut | Native | Standard |
| ClickUp | Native | Standard |

### CRM & Customer Success
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Salesforce | Native | Standard |
| Zendesk | Native | Standard |
| HubSpot | Native | Standard |
| Intercom | Native | Standard |
| Freshdesk | Native | Standard |
| ServiceNow | Native | Configuration |
| Gainsight | Native | Configuration |
| ChurnZero | Native | Configuration |

### HR & People Operations
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Workday | Native | Configuration |
| BambooHR | Native | Standard |
| Greenhouse | Native | Standard |
| Lever | Native | Standard |
| Lattice | Native | Standard |
| Culture Amp | Native | Configuration |
| Rippling | Native | Standard |

### Finance & Operations
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| NetSuite | Native | Configuration |
| Coupa | Native | Configuration |
| Expensify | Native | Standard |
| Bill.com | Native | Standard |
| Carta | Native | Configuration |

### Data & Analytics
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Looker | Native | Standard |
| Tableau | Native | Configuration |
| Power BI | Native | Configuration |
| Amplitude | Native | Standard |
| Mixpanel | Native | Standard |
| Snowflake | Native | Configuration |
| Databricks | Native | Configuration |

### Security & IT
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Okta | Native | Standard |
| OneLogin | Native | Standard |
| Azure AD | Native | Standard |
| PagerDuty | Native | Standard |
| Datadog | Native | Standard |
| Splunk | Native | Configuration |

### Email & Calendar
| Connector | Status | Implementation Tier |
|-----------|--------|---------------------|
| Gmail | Native | Standard |
| Outlook | Native | Standard |
| Google Calendar | Native | Standard |
| Outlook Calendar | Native | Standard |

---

## Implementation Tier Definitions

### Standard Implementation
**Timeline:** < 14 days

**Characteristics:**
- Pre-built native connector available
- OAuth or API key authentication
- No custom field mapping required
- Standard data model alignment
- Self-service configuration possible

**Included Services:**
- Connector activation and authentication
- Basic permission sync
- Default search configuration
- Standard onboarding session

---

### Configuration Implementation
**Timeline:** 14-30 days

**Characteristics:**
- Native connector with custom configuration needs
- Custom field mapping required
- Advanced permission models
- Multiple instance support
- Specialized data filtering

**Included Services:**
- All Standard services
- Custom field mapping workshop
- Advanced permission configuration
- Custom search tuning
- Dedicated implementation manager

---

### Customization Implementation
**Timeline:** 30-60 days

**Characteristics:**
- Native connector with significant modifications
- Custom metadata extraction
- Integration with client-specific workflows
- Advanced security requirements
- Multi-system orchestration

**Included Services:**
- All Configuration services
- Custom development hours (up to 40)
- Security review and compliance documentation
- Custom training materials
- Extended support period

---

### Custom Implementation (Custom Build)
**Timeline:** > 30 days (typically 60-120 days)

**Characteristics:**
- No native connector available
- Requires net-new connector development
- Client-specific data sources
- Complex authentication requirements
- Unique data models

**Requirements:**
- **Client MUST provide a REST API** for data access
- API documentation required
- Test environment access
- Dedicated client technical resource
- Executive sponsor commitment

**Included Services:**
- Full custom connector development
- API integration design
- Custom authentication implementation
- Comprehensive testing suite
- Dedicated engineering team
- Ongoing maintenance agreement

---

## Custom Connector Specifications

### Mandatory Client Requirements

For any Custom Connector engagement, the client **MUST** provide:

1. **REST API Access**
   - Well-documented REST API endpoints
   - Authentication mechanism (OAuth 2.0 preferred, API key acceptable)
   - Rate limiting specifications
   - Sandbox/test environment

2. **API Capabilities**
   - List/enumerate content endpoints
   - Full content retrieval endpoints
   - Incremental sync support (created/modified timestamps)
   - Permission/ACL endpoints (if applicable)

3. **Technical Resources**
   - Designated API point of contact
   - Access to API support team
   - Timely response to technical queries (< 24 hours)

4. **Documentation**
   - Complete API reference documentation
   - Authentication flow documentation
   - Data model/schema documentation
   - Error code reference

### API Minimum Specifications

```json
{
  "required_endpoints": {
    "list_content": "GET /api/v1/content",
    "get_content": "GET /api/v1/content/{id}",
    "get_permissions": "GET /api/v1/content/{id}/permissions"
  },
  "required_features": {
    "pagination": true,
    "incremental_sync": true,
    "filtering_by_date": true
  },
  "authentication": {
    "supported": ["oauth2", "api_key", "jwt"],
    "preferred": "oauth2"
  },
  "rate_limits": {
    "minimum_requests_per_minute": 100,
    "recommended_requests_per_minute": 1000
  }
}
```

---

## Solution Mapping Quick Reference

| Customer Need | Recommended Solution | Implementation Tier |
|---------------|---------------------|---------------------|
| Search across SaaS apps | Native connectors | Standard |
| Unified knowledge base | Glean + Confluence/Notion | Standard |
| Engineering docs search | GitHub + Jira integration | Standard |
| Customer context | Salesforce + Zendesk | Standard |
| Internal wiki migration | Custom content import | Configuration |
| Legacy system integration | Custom connector | Custom Build |
| Proprietary database search | Custom connector | Custom Build |
| On-premise systems | Glean Edge + Custom | Custom Build |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-01 | Initial catalog release |
| 1.1 | 2024-03-15 | Added 15 new native connectors |
| 1.2 | 2024-06-01 | Updated implementation tier definitions |
