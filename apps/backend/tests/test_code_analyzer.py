from app.tools.code_analyzer_tool import analyze_c_code_light


def _issue_types(code: str) -> list[str]:
    return [issue["type"] for issue in analyze_c_code_light(code)]


def test_detects_scanf_missing_address():
    issues = analyze_c_code_light('int main(){ int n; scanf("%d", n); return 0; }')

    assert issues[0]["type"] == "scanf_missing_address"
    assert issues[0]["severity"] == "high"
    assert issues[0]["message"]


def test_detects_assignment_in_condition():
    issues = analyze_c_code_light("int main(){ int x=1; if (x = 2) return 1; return 0; }")

    assert issues[0]["type"] == "assignment_in_condition"
    assert issues[0]["severity"] == "medium"
    assert issues[0]["message"]


def test_detects_array_boundary_risk():
    issues = analyze_c_code_light("int main(){ int a[10]; int n=10; for(int i=0; i<=n; i++) a[i]=0; }")

    assert issues[0]["type"] == "array_boundary_risk"
    assert issues[0]["severity"] == "medium"
    assert issues[0]["message"]


def test_detects_binary_search_boundary_risk():
    issues = analyze_c_code_light("int main(){ int left=0, mid=0; left = mid; return 0; }")

    assert issues[0]["type"] == "binary_search_boundary_risk"
    assert issues[0]["severity"] == "medium"
    assert issues[0]["message"]


def test_detects_uninitialized_variable_risk():
    issues = analyze_c_code_light('int main(){ int n; printf("%d", n); return 0; }')

    assert issues[0]["type"] == "uninitialized_variable_risk"
    assert issues[0]["severity"] == "medium"
    assert issues[0]["message"]


def test_detects_scanf_argument_count_mismatch():
    issues = analyze_c_code_light('int main(){ int a,b; scanf("%d %d", &a); return 0; }')

    assert "scanf_argument_count_mismatch" in _issue_types('int main(){ int a,b; scanf("%d %d", &a); return 0; }')
    assert issues[0]["severity"] == "high"


def test_detects_loop_update_missing():
    issues = analyze_c_code_light("int main(){ for(int i=0; i<10;) printf(\"%d\", i); return 0; }")

    assert "loop_update_missing" in [issue["type"] for issue in issues]


def test_detects_infinite_loop_risk():
    issues = analyze_c_code_light('int main(){ while(1){ printf("x"); } return 0; }')

    assert "infinite_loop_risk" in [issue["type"] for issue in issues]


def test_detects_recursive_base_case_missing():
    issues = analyze_c_code_light("int f(int n){ return n * f(n - 1); }")

    assert "recursive_base_case_missing" in [issue["type"] for issue in issues]


def test_detects_string_missing_terminator_risk():
    issues = analyze_c_code_light("int main(){ char s[3]; s[0]='a'; s[1]='b'; printf(\"%s\", s); return 0; }")

    assert "string_missing_terminator_risk" in [issue["type"] for issue in issues]


def test_returns_empty_for_clean_code():
    code = 'int main(){ int n = 1; printf("%d", n); return 0; }'

    assert analyze_c_code_light(code) == []


def test_detects_multiple_issues():
    code = """
    int main(){
        int n;
        scanf("%d", n);
        if (n = 3) return 1;
        return 0;
    }
    """

    assert {"scanf_missing_address", "assignment_in_condition"}.issubset(set(_issue_types(code)))
