"""Document-store adapters."""

from .filesystem_checks_catalog_repository import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
)
from .filesystem_feature_state import (
    archive_completed_feature,
    discover_active_feature_paths,
    done_features_pending_archive,
    evaluate_initial_feature_load,
    pending_features,
    ready_for_active_iteration,
    refresh_feature_after_implement,
    resolve_feature_paths,
    restore_archived_feature,
    set_status,
    should_archive_selected_feature,
    touch_active_feature_for_iteration,
)
from .filesystem_feature_specification_repository import (
    FilesystemFeatureSpecificationRepository,
)
from .filesystem_guidance_topic_repository import FilesystemGuidanceTopicRepository

__all__ = [
    "ChecksCatalogLoadOptions",
    "FilesystemChecksCatalogRepository",
    "FilesystemFeatureSpecificationRepository",
    "FilesystemGuidanceTopicRepository",
    "archive_completed_feature",
    "discover_active_feature_paths",
    "done_features_pending_archive",
    "evaluate_initial_feature_load",
    "pending_features",
    "ready_for_active_iteration",
    "refresh_feature_after_implement",
    "resolve_feature_paths",
    "restore_archived_feature",
    "set_status",
    "should_archive_selected_feature",
    "touch_active_feature_for_iteration",
]
