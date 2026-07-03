from sqlalchemy.orm import Session
from app.database import SessionLocal, Base
Base.registry.dispose()
from app.models import AssessmentTemplate, Question, Applicant, Assessment, CountryProfile, CountryTier, Base as ModelsBase
import app.models as models_mod
print("registered tables:", list(ModelsBase.metadata.tables.keys()))
Base.metadata.create_all(bind=SessionLocal().bind)

db: Session = SessionLocal()
try:
    for table in [db.query(models_mod.Answer).delete(), db.query(models_mod.Assessment).delete(), db.query(models_mod.Applicant).delete(), db.query(models_mod.Question).delete(), db.query(models_mod.AssessmentTemplate).delete(), db.query(models_mod.CountryProfile).delete()]:
        pass
    db.commit()

    countries = [
        ("Ukraine", CountryTier.HIGH),
        ("Poland", CountryTier.HIGH),
        ("Philippines", CountryTier.HIGH),
        ("Vietnam", CountryTier.HIGH),
        ("India", CountryTier.MEDIUM),
        ("Nepal", CountryTier.MEDIUM),
        ("Bangladesh", CountryTier.LOW),
        ("North Korea", CountryTier.KNOCKOUT),
        ("Nicaragua", CountryTier.KNOCKOUT),
    ]
    for name, tier in countries:
        db.add(CountryProfile(country_name=name, tier=tier))
    db.commit()

    tpl = AssessmentTemplate(name="GDI Recruitment Screening", description="Initial screening for Asia→Poland workers", version="0.1.0")
    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    questions = [
        (1, "country", "What country are you from?", "select", ["Ukraine","Poland","Philippines","Vietnam","India","Nepal","Bangladesh","Nicaragua","North Korea"], True, True, 1.0, 1.0, "Your country of citizenship"),
        (2, "current_country", "In which country are you currently living?", "text", [], True, False, 0.3, 0.5, ""),
        (3, "embassy_country", "In which country is the Polish Embassy/Consulate where you can apply for a visa?", "text", [], True, False, 0.3, 0.5, ""),
        (4, "passport_valid", "Do you have a valid international passport?", "select", ["Yes","No"], True, True, 1.0, 1.0, "Required for visa application"),
        (5, "passport_expiry", "Passport expiry date", "text", [], True, False, 0.3, 0.5, ""),
        (6, "position", "What position are you applying for?", "select", ["Welder","Helper","Driver","Other"], True, False, 0.5, 0.8, ""),
        (7, "welding_methods", "Which welding methods do you use? (only if Welder)", "text", [], False, False, 0.3, 0.4, ""),
        (8, "years_experience", "How many years of experience do you have?", "text", [], True, False, 0.8, 0.9, ""),
        (9, "previous_work", "Describe your previous work experience.", "textarea", [], True, False, 0.5, 0.7, ""),
        (10, "worked_abroad", "Have you worked abroad before?", "select", ["Yes","No"], True, False, 0.5, 0.6, ""),
        (11, "technical_drawings", "Can you read technical drawings?", "select", ["Yes","No"], True, False, 0.8, 0.7, ""),
        (12, "work_independently", "Can you work independently or only with supervision?", "select", ["Independently","Both","Only with supervision"], True, False, 0.8, 0.7, ""),
        (13, "materials_worked", "What materials have you worked with?", "textarea", [], False, False, 0.4, 0.5, ""),
        (14, "can_send_photos", "Can you send photos/videos of your work?", "select", ["Yes","No"], True, False, 0.3, 0.4, ""),
        (15, "can_record_video", "If we ask you to record a short video, can you do it?", "select", ["Yes","No"], True, False, 0.3, 0.4, ""),
        (16, "english_level", "Do you speak English?", "select", ["Native","C2","C1","B2","B1","A2","A1","No"], True, False, 1.0, 0.9, ""),
        (17, "ready_to_wait", "Are you ready to wait around 3 months for visa processing?", "select", ["Yes","No"], True, False, 0.7, 0.6, ""),
        (18, "understands_process", "Do you understand the recruitment process?", "select", ["Yes","No"], True, False, 0.5, 0.5, ""),
        (19, "duration", "How long do you want to come to Poland for?", "select", ["1 year","2 years","3+ years","Permanent"], True, False, 0.5, 0.6, ""),
        (20, "working_hours", "How many working hours per week are you ready to work?", "text", [], True, False, 0.5, 0.5, ""),
        (21, "expected_salary", "What monthly NET salary do you expect?", "text", [], True, False, 0.4, 0.5, ""),
        (22, "financial_readiness", "Do you have money for visa/travel costs?", "select", ["Yes","No"], True, True, 1.0, 1.0, "Required"),
        (23, "knows_costs", "Do you know approximately how much these costs are?", "select", ["Yes","No"], False, False, 0.3, 0.3, ""),
        (24, "married_children", "Are you married or do you have children?", "select", ["No","Married, no children","Married with children","Single with children"], False, False, 0.2, 0.2, ""),
        (25, "health_problems", "Do you have any health problems?", "select", ["No","Yes"], True, True, 1.0, 1.0, "Major health issues are disqualifying"),
        (26, "visa_applied_before", "Have you ever applied for a visa before?", "select", ["Yes","No"], False, False, 0.3, 0.3, ""),
        (27, "visa_refused", "Have you ever been refused a visa?", "select", ["Yes","No"], True, True, 1.0, 1.0, "Previous refusal may affect eligibility"),
        (28, "police_problems", "Have you ever had problems with police, immigration or deportation?", "select", ["Yes","No"], True, True, 1.0, 1.0, ""),
        (29, "legal_work_only", "Are you ready to work legally only?", "select", ["Yes","No"], True, True, 1.0, 1.0, ""),
        (30, "motivation", "Why do you want to work in Poland?", "textarea", [], True, False, 0.5, 0.6, ""),
    ]

    import secrets
    for order, key, label, qtype, options, required, is_knockout, severity, weight, *rest in questions:
        db.add(models_mod.Question(
            template_id=tpl.id,
            order=order,
            key=key,
            label=label,
            question_type=qtype,
            options=options,
            required=required,
            is_knockout=is_knockout,
            severity=severity,
            weight=weight,
            description=rest[0] if rest else "",
        ))
    db.commit()

    applicant = models_mod.Applicant(full_name="Test Candidate", email="test@example.com", phone="+380000000000", country="Ukraine")
    db.add(applicant)
    db.commit()
    db.refresh(applicant)
    token = secrets.token_urlsafe(32)
    assessment = models_mod.Assessment(applicant_id=applicant.id, template_id=tpl.id, token=token, status=models_mod.ApplicationStatus.DRAFT)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    print(f"template_id={tpl.id}")
    print(f"questions={len(questions)}")
    print(f"assessment_id={assessment.id}")
    print(f"token={token}")
    print(f"link=http://127.0.0.1:8000/assessment/{token}")
finally:
    db.close()
