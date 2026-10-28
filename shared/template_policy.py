"""Select only trusted, account-scoped configured reply templates."""

from contracts.templates import ApprovedTemplate, TemplatePayload


def select_reply_template(
    templates: list[ApprovedTemplate], selected_key, *, business_id, phone_number_id, reply_text
):
    matches = [t for t in templates if t.key == selected_key]
    if len(matches) != 1:
        return None, "approved_template_required"
    template = matches[0]
    if template.business_id != business_id or template.phone_number_id != phone_number_id:
        return None, "template_account_mismatch"
    values = []
    for parameter in template.body_parameters:
        value = reply_text if parameter.source == "reply_text" else parameter.literal
        if not isinstance(value, str) or not value.strip() or len(value) > parameter.max_length:
            return None, "template_parameter_invalid"
        values.append(value)
    return TemplatePayload(
        key=template.key,
        name=template.name,
        language=template.language,
        body_parameters=tuple(values),
    ), None
