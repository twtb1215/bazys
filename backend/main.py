
@app.get("/assessment/{token}")
def assessment_page(request: Request, token: str):
    return templates.TemplateResponse("assessment.html", {
        "request": request, "token": token
    })
