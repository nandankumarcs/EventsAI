from django.db import models


class EventBase(models.Model):
    listing_code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    event_date = models.DateField(db_index=True)
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(null=True, blank=True)
    city = models.CharField(max_length=120, db_index=True)
    state = models.CharField(max_length=120, blank=True)
    venue_name = models.CharField(max_length=255, db_index=True)
    venue_area = models.CharField(max_length=255, blank=True)
    venue_address = models.TextField(blank=True)
    languages = models.JSONField(default=list, blank=True)
    min_price = models.PositiveIntegerField(default=0)
    max_price = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    source_label = models.CharField(max_length=64, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["city", "event_date"], name="%(class)s_city_date_idx"),
            models.Index(fields=["venue_name", "event_date"], name="%(class)s_venue_date_idx"),
            models.Index(fields=["start_at"], name="%(class)s_start_at_idx"),
        ]


class MovieEvent(EventBase):
    release_date = models.DateField(null=True, blank=True, db_index=True)
    runtime_minutes = models.PositiveIntegerField(default=120)
    certification = models.CharField(max_length=32, blank=True)
    genres = models.JSONField(default=list, blank=True)
    cast = models.JSONField(default=list, blank=True)
    directors = models.JSONField(default=list, blank=True)
    formats = models.JSONField(default=list, blank=True)
    franchise = models.CharField(max_length=120, blank=True)
    synopsis = models.TextField(blank=True)
    viewer_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    content_origin = models.CharField(max_length=32, blank=True)

    class Meta(EventBase.Meta):
        db_table = "movie_events"
        ordering = ["event_date", "start_at", "title"]
        indexes = EventBase.Meta.indexes + [
            models.Index(fields=["title"], name="movie_title_idx"),
            models.Index(fields=["release_date"], name="movie_release_date_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class SportEvent(EventBase):
    sport_type = models.CharField(max_length=64, db_index=True)
    tournament_name = models.CharField(max_length=255, db_index=True)
    season_label = models.CharField(max_length=64, blank=True)
    competition_stage = models.CharField(max_length=64, blank=True)
    format_label = models.CharField(max_length=64, blank=True)
    home_team = models.CharField(max_length=120, db_index=True)
    away_team = models.CharField(max_length=120, db_index=True)
    participant_names = models.JSONField(default=list, blank=True)
    featured_athletes = models.JSONField(default=list, blank=True)
    organizer = models.CharField(max_length=255, blank=True)
    gate_open_at = models.DateTimeField(null=True, blank=True)
    match_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta(EventBase.Meta):
        db_table = "sport_events"
        ordering = ["event_date", "start_at", "sport_type", "tournament_name"]
        indexes = EventBase.Meta.indexes + [
            models.Index(fields=["sport_type", "event_date"], name="sport_type_date_idx"),
            models.Index(fields=["tournament_name"], name="sport_tournament_idx"),
            models.Index(fields=["home_team"], name="sport_home_team_idx"),
            models.Index(fields=["away_team"], name="sport_away_team_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.home_team} vs {self.away_team}"
