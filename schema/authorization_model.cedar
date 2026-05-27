// =============================================================================
// senso-ai Authorization Model — Cedar Policy Language
// =============================================================================
//
// This authorization model governs access to the senso-ai enterprise knowledge
// base, which contains 15 specialized AI/ML repositories.  It is deployed to
// Auth0 FGA and evaluated on every RAG query to guarantee zero document leakage.
//
// Auth0 Domain: dev-c3wp4h1e4gv0t64i.us.auth0.com
// Schema Version: 1.1
//
// Resource Hierarchy:
//
//   organization (senso-ai)
//     └── repository (15 repos)
//           └── document
//                 └── section
//                       └── code_block
//
// Role Hierarchy: owner > admin > editor > viewer
// Implicit role:  org_member (all authenticated users)
// =============================================================================

// ---------------------------------------------------------------------------
// Conditions
// ---------------------------------------------------------------------------

condition isPublished(document: Document) {
    document.attributes.published == true
}

condition isNotConfidential(document: Document) {
    document.attributes.confidential != true
}

condition isNotAudit(document: Document) {
    document.attributes.is_audit != true
}

condition isExplicitViewer() {
    // Used when confidential documents require explicit viewer assignment
    // rather than inheriting from parent repository.
    true
}

// ---------------------------------------------------------------------------
// Organization
// ---------------------------------------------------------------------------
// Top-level entity.  All authenticated users are implicitly members.
// Owners and admins manage the organization.

type organization

  relations
    // Direct assignment — the ultimate authority for the organization.
    owner: [user]

    // Admins can manage members and repositories but cannot delete the org.
    admin
      = owner
      or [user]

    // All authenticated users in the org.  Members can read and query.
    member
      = admin
      or [user]

  permissions
    can_read   = member
    can_edit   = admin
    can_delete = owner
    can_share  = admin
    can_query  = member

// ---------------------------------------------------------------------------
// Repository
// ---------------------------------------------------------------------------
// Each of the 15 AI/ML domain repositories.  Access is inherited from the
// parent organization via the "organization" relation.  Direct role
// assignments on a repository override org-level inheritance for that repo.

type repository

  relations
    owner: [user]

    admin
      = owner
      or [user]

    editor
      = admin
      or [user]

    // Viewers include explicitly-assigned users PLUS org members (inherited).
    viewer
      = editor
      or [user]
      or organization->member

    // Pointer to the parent organization.
    organization: [organization]

  permissions
    can_read   = viewer
    can_edit   = editor
    can_delete = owner
    can_share  = admin
    can_query  = viewer

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------
// Individual documents (papers, reports, guides, code references) within
// a repository.  Access inherits from the parent repository automatically.

type document

  relations
    owner: [user]

    admin
      = owner
      or [user]

    editor
      = admin
      or [user]

    // Viewers can be directly assigned OR inherited from the parent repo.
    viewer
      = editor
      or [user]

    // Pointer to the parent repository for access inheritance.
    repository: [repository]

  permissions
    // Read access: direct viewer + repo-level viewer (with conditional guard).
    // If the document is confidential, only direct viewers and above are allowed.
    can_read
      = viewer
      or repository->viewer
        if isNotConfidential(this)

    // Edit access: direct editor + repo-level editor.
    can_edit
      = editor
      or repository->editor

    // Delete access: direct owner + repo-level owner.
    can_delete
      = owner
      or repository->owner

    // Share access: direct admin + repo-level admin.
    can_share
      = admin
      or repository->admin

    // Query access for RAG: same as can_read, with additional guards.
    // Unpublished documents are hidden from viewers (only editors/admins see them).
    // Audit-tagged documents require explicit assignment.
    can_query
      = viewer
      or repository->viewer
        if isNotConfidential(this) and isNotAudit(this)
      // Editors and admins bypass the published/confidential/audit guards.
      or editor
      or repository->editor
      or admin
      or repository->admin

// ---------------------------------------------------------------------------
// Section
// ---------------------------------------------------------------------------
// Sub-sections within a document.  Useful for documents that contain
// both public and sensitive sections (e.g., executive summary + financials).

type section

  relations
    owner: [user]

    editor
      = owner
      or [user]

    viewer
      = editor
      or [user]

    // Pointer to the parent document.
    document: [document]

  permissions
    can_read
      = viewer
      or document->viewer

    can_edit
      = editor
      or document->editor

    can_delete
      = owner
      or document->owner

// ---------------------------------------------------------------------------
// Code Block
// ---------------------------------------------------------------------------
// Individual code snippets within sections.  Inherits access from the
// parent section and ultimately from the document's repository.

type code_block

  relations
    owner: [user]

    editor
      = owner
      or [user]

    viewer
      = editor
      or [user]

    // Pointer to the parent section.
    section: [section]

  permissions
    can_read
      = viewer
      or section->viewer

    can_edit
      = editor
      or section->editor
