from django.db import models
from django.utils import timezone

from apps.core.models import UUIDTimeStampedModel


class ChatThread(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        BOOKED = "booked", "Booked"
        ARCHIVED = "archived", "Archived"
        DELETED = "deleted", "Deleted"

    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=Status, default=Status.ACTIVE)
    last_message_preview = models.CharField(max_length=500, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_threads"
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["status", "-last_activity_at"], name="thread_status_recent_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class ChatMessage(UUIDTimeStampedModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"
        TOOL = "tool", "Tool"

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    position = models.PositiveIntegerField()
    role = models.CharField(max_length=24, choices=Role)
    content = models.TextField()
    tool_name = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "position"],
                name="unique_message_position_per_thread",
            )
        ]
        indexes = [
            models.Index(fields=["thread", "position"], name="thread_message_order_idx"),
            models.Index(fields=["role"], name="chat_message_role_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.role}:{self.position}"


class ThreadFilter(UUIDTimeStampedModel):
    thread = models.OneToOneField(
        ChatThread,
        on_delete=models.CASCADE,
        related_name="filter_state",
    )
    active_filters = models.JSONField(default=dict, blank=True)
    latest_result_context = models.JSONField(default=dict, blank=True)
    pending_booking = models.JSONField(default=dict, blank=True)
    resolver_trace = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    last_resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "thread_filters"

    def __str__(self) -> str:
        return f"filters:{self.thread_id}"
