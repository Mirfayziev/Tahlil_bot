"""Marshmallow validatsiya sxemalari (TZ v2, bo'lim 2: API)."""
from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=1))
    password = fields.Str(required=True, validate=validate.Length(min=1))


class RefreshSchema(Schema):
    refresh_token = fields.Str(required=True)


class CompleteAssignmentSchema(Schema):
    report_text = fields.Str(required=True, validate=validate.Length(min=1, max=4000))
    time_spent_minutes = fields.Int(required=False, allow_none=True, validate=validate.Range(min=0))


class RespondAssignmentSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(["qabul_qilindi", "rad_etildi"]))
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
