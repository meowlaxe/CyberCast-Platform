from CTFd.plugins.ctfd_student_teams.models import (
    StudentTeam,
    StudentTeamInvite,
    StudentTeamJoinRequest,
    StudentTeamMember,
    StudentTeamScoreCache,
    StudentTeamScoreEvent,
)
from CTFd.plugins.ctfd_student_teams.routes import student_teams_bp


def test_student_teams_plugin_models_have_expected_tables():
    assert StudentTeam.__tablename__ == "st_teams"
    assert StudentTeamMember.__tablename__ == "st_team_members"
    assert StudentTeamInvite.__tablename__ == "st_team_invites"
    assert StudentTeamJoinRequest.__tablename__ == "st_team_join_requests"
    assert StudentTeamScoreEvent.__tablename__ == "st_team_score_events"
    assert StudentTeamScoreCache.__tablename__ == "st_team_score_cache"


def test_student_teams_blueprint_contract():
    assert student_teams_bp.name == "student_teams"
    assert student_teams_bp.url_prefix == "/plugins/platform-plus"
