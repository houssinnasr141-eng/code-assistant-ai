
from flask import Flask, request, jsonify, send_from_directory
import ast
import builtins
import keyword
import re
import symtable

app = Flask(__name__)

MAX_CODE_SIZE = 30000


# -----------------------------------------
# EXPLANATIONS
# -----------------------------------------

EXPLANATIONS = {
    "ZeroDivisionError": {
        "explanation": (
            "Your code attempts to divide a number by zero. "
            "Python cannot perform this mathematical operation."
        ),
        "fix": (
            "Use a variable or expression whose value is not zero. "
            "If the divisor comes from user input, check it before division."
        )
    },
    "NameError": {
        "explanation": (
            "Your code uses a name that Python cannot find. "
            "It may be misspelled or may not have been defined or imported."
        ),
        "fix": (
            "Check the spelling of the name and make sure it is defined "
            "or imported before it is used."
        )
    },
    "TypeError": {
        "explanation": (
            "This operation appears to combine incompatible data types. "
            "For example, adding a string to a number."
        ),
        "fix": (
            "Convert the values to compatible types, for example with "
            "int(), float(), or str(), when appropriate."
        )
    },
    "SyntaxError": {
        "explanation": (
            "Python cannot understand the structure of this statement. "
            "There may be a missing colon, bracket, quote, or operator."
        ),
        "fix": (
            "Review the reported line and the line immediately before it. "
            "Check brackets, quotes, colons, and operators."
        )
    },
    "IndentationError": {
        "explanation": (
            "The indentation of this line does not match Python's block "
            "structure. Python uses indentation to identify code blocks."
        ),
        "fix": (
            "Use consistent indentation. Four spaces per indentation "
            "level is a common Python convention."
        )
    },
    "PossibleInfiniteLoop": {
        "explanation": (
            "This while loop uses a condition that is always true. "
            "If the loop never exits with break or another control path, "
            "it may run indefinitely."
        ),
        "fix": (
            "Add a condition that can become false, or add a suitable "
            "break statement when the intended stopping condition is met."
        )
    },
    "EmptyRange": {
        "explanation": (
            "This for loop uses an empty range, so its body will not run."
        ),
        "fix": (
            "Check the start, stop, and step values passed to range()."
        )
    },
    "FunctionCall": {
        "explanation": (
            "This function name may not exist in the current program "
            "or may not have been imported."
        ),
        "fix": (
            "Check the function name and define it or import it "
            "before calling it."
        )
    }
}


def create_issue(line, category, message, severity="error",
                 explanation=None, suggestion=None):

    details = EXPLANATIONS.get(category, {})

    return {
        "line": line or 1,
        "category": category,
        "message": message,
        "severity": severity,
        "explanation": explanation or details.get(
            "explanation", "Review this part of your code."
        ),
        "suggestion": suggestion or details.get(
            "fix", "Review this statement and check its logic."
        )
    }


# -----------------------------------------
# SYNTAX ANALYSIS
# -----------------------------------------

def check_syntax(code):
    try:
        return ast.parse(code), None

    except IndentationError as error:
        issue = create_issue(
            error.lineno,
            "IndentationError",
            error.msg or "Incorrect indentation."
        )
        return None, issue

    except SyntaxError as error:
        issue = create_issue(
            error.lineno,
            "SyntaxError",
            error.msg or "Invalid Python syntax."
        )
        return None, issue


# -----------------------------------------
# VARIABLE TYPE ANALYSIS
# -----------------------------------------

def get_value_type(node, variables):

    if isinstance(node, ast.Constant):
        return type(node.value)

    if isinstance(node, ast.Name):
        return variables.get(node.id)

    if isinstance(node, ast.List):
        return list

    if isinstance(node, ast.Tuple):
        return tuple

    if isinstance(node, ast.Dict):
        return dict

    if isinstance(node, ast.Set):
        return set

    if isinstance(node, ast.JoinedStr):
        return str

    return None


def collect_variable_types(tree):

    variables = {}

    for node in ast.walk(tree):

        if isinstance(node, ast.Assign):

            value_type = get_value_type(node.value, variables)

            for target in node.targets:
                if isinstance(target, ast.Name):
                    variables[target.id] = value_type

        elif isinstance(node, ast.AnnAssign):

            value_type = get_value_type(node.value, variables)

            if isinstance(node.target, ast.Name):
                variables[node.target.id] = value_type

    return variables


# -----------------------------------------
# ZERO DIVISION ANALYSIS
# -----------------------------------------

def check_zero_division(tree):

    issues = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.BinOp):
            continue

        if not isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            continue

        right = node.right

        if (
            isinstance(right, ast.Constant)
            and type(right.value) in (int, float)
            and right.value == 0
        ):

            issues.append(create_issue(
                node.lineno,
                "ZeroDivisionError",
                "Possible division by zero."
            ))

    return issues


# -----------------------------------------
# TYPE ERROR ANALYSIS
# -----------------------------------------

def check_type_errors(tree, variables):

    issues = []
    numeric_types = (int, float, complex)

    for node in ast.walk(tree):

        if not isinstance(node, ast.BinOp):
            continue

        left_type = get_value_type(node.left, variables)
        right_type = get_value_type(node.right, variables)

        if left_type is None or right_type is None:
            continue

        invalid = False

        if isinstance(node.op, ast.Add):

            invalid = (
                (left_type is str and right_type in numeric_types)
                or
                (right_type is str and left_type in numeric_types)
            )

        elif isinstance(
            node.op,
            (ast.Sub, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
        ):

            invalid = (
                left_type is str or right_type is str
            )

        if invalid:

            issues.append(create_issue(
                node.lineno,
                "TypeError",
                "Incompatible data types in this operation."
            ))

    return issues


# -----------------------------------------
# VARIABLE AND FUNCTION ANALYSIS
# -----------------------------------------

def check_undefined_names(code):

    issues = []

    try:
        table = symtable.symtable(code, "<user_code>", "exec")

        module_names = set()

        for symbol in table.get_symbols():

            if (
                symbol.is_assigned()
                or symbol.is_imported()
                or symbol.is_namespace()
            ):
                module_names.add(symbol.get_name())

        builtin_names = set(dir(builtins))

        def inspect_scope(scope):

            for symbol in scope.get_symbols():

                name = symbol.get_name()

                if (
                    symbol.is_global()
                    and symbol.is_referenced()
                    and not symbol.is_assigned()
                    and not symbol.is_imported()
                    and name not in module_names
                    and name not in builtin_names
                    and not keyword.iskeyword(name)
                ):

                    is_function_call = False

                    # The symbol table identifies an unknown global name.
                    # We classify it as a possible function if its name
                    # appears as a direct function call.
                    for node in ast.walk(ast.parse(code)):
                        if (
                            isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Name)
                            and node.func.id == name
                        ):
                            is_function_call = True
                            break

                    category = (
                        "FunctionCall" if is_function_call else "NameError"
                    )

                    issues.append(create_issue(
                        scope.get_lineno(),
                        category,
                        f"Possible undefined name: '{name}'.",
                        severity="warning",
                        explanation=(
                            f"The name '{name}' is used but was not found "
                            "among the known global definitions or imports."
                        ),
                        suggestion=(
                            f"Check the spelling of '{name}', define it, "
                            "or import it before using it."
                        )
                    ))

            for child in scope.get_children():
                inspect_scope(child)

        inspect_scope(table)

    except (SyntaxError, ValueError):
        pass

    # Avoid duplicate reports for the same name and line.
    unique = {}
    for issue in issues:
        key = (issue["line"], issue["message"])
        unique[key] = issue

    return list(unique.values())


# -----------------------------------------
# LOOP ANALYSIS
# -----------------------------------------

def check_loops(tree):

    issues = []
    loop_details = []

    for node in ast.walk(tree):

        if isinstance(node, ast.For):

            description = "For loop"

            if (
                isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
                and len(node.iter.args) == 1
                and isinstance(node.iter.args[0], ast.Constant)
                and isinstance(node.iter.args[0].value, int)
                and node.iter.args[0].value <= 0
            ):

                issues.append(create_issue(
                    node.lineno,
                    "EmptyRange",
                    "This range() loop has no iterations.",
                    severity="warning"
                ))

            loop_details.append({
                "line": node.lineno,
                "type": description,
                "explanation": (
                    "A for loop repeats its body for each item "
                    "provided by its iterable."
                ),
                "suggestion": (
                    "Check the iterable and the loop variable. "
                    "Make sure the loop covers the intended items."
                )
            })

        elif isinstance(node, ast.While):

            description = "While loop"

            always_true = (
                isinstance(node.test, ast.Constant)
                and node.test.value is True
            )

            has_break = any(
                isinstance(child, ast.Break)
                for child in ast.walk(node)
            )

            if always_true and not has_break:

                issues.append(create_issue(
                    node.lineno,
                    "PossibleInfiniteLoop",
                    "This while True loop has no detected break statement.",
                    severity="warning"
                ))

            loop_details.append({
                "line": node.lineno,
                "type": description,
                "explanation": (
                    "A while loop repeats while its condition evaluates "
                    "to True."
                ),
                "suggestion": (
                    "Make sure the condition can eventually become False, "
                    "or provide a suitable exit condition."
                )
            })

    return issues, loop_details


# -----------------------------------------
# CODE STYLE AND SECURITY
# -----------------------------------------

def check_style(code, tree):

    issues = []

    for number, line in enumerate(code.splitlines(), start=1):

        if len(line) > 100:

            issues.append(create_issue(
                number,
                "CodeStyle",
                "This line is longer than 100 characters.",
                severity="info",
                explanation=(
                    "Long lines can make code harder to read."
                ),
                suggestion=(
                    "Consider splitting this statement into shorter lines."
                )
            ))

        if line.rstrip() != line:

            issues.append(create_issue(
                number,
                "CodeStyle",
                "This line contains trailing spaces.",
                severity="info",
                explanation=(
                    "Spaces at the end of a line are usually unnecessary."
                ),
                suggestion="Remove the extra spaces at the end of the line."
            ))

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            if isinstance(node.func, ast.Name):

                if node.func.id in ("eval", "exec"):

                    issues.append(create_issue(
                        node.lineno,
                        "Security",
                        f"Use of {node.func.id}() detected.",
                        severity="warning",
                        explanation=(
                            "These functions can execute dynamically "
                            "constructed Python code and require careful "
                            "handling of untrusted input."
                        ),
                        suggestion=(
                            "Avoid using them with untrusted input. "
                            "Prefer safer, specific alternatives."
                        )
                    ))

    return issues


# -----------------------------------------
# CODE STATISTICS
# -----------------------------------------

def get_statistics(code, tree):

    nodes = list(ast.walk(tree))
    lines = code.splitlines()

    return {
        "total_lines": len(lines),
        "non_empty_lines": sum(
            1 for line in lines if line.strip()
        ),
        "functions": sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in nodes
        ),
        "classes": sum(
            isinstance(node, ast.ClassDef)
            for node in nodes
        ),
        "imports": sum(
            isinstance(node, (ast.Import, ast.ImportFrom))
            for node in nodes
        )
    }


# -----------------------------------------
# SAFE AUTOMATIC FIXES
# -----------------------------------------

def generate_fixed_code(code):

    fixed = code
    changes = []

    # Remove trailing whitespace without changing program logic.
    lines = fixed.splitlines(keepends=True)
    cleaned_lines = []

    for line in lines:

        if line.endswith("\r\n"):
            cleaned = line[:-2].rstrip(" \t") + "\r\n"
        elif line.endswith("\n"):
            cleaned = line[:-1].rstrip(" \t") + "\n"
        else:
            cleaned = line.rstrip(" \t")

        if cleaned != line:
            changes.append(
                "Removed unnecessary spaces at the end of a line."
            )

        cleaned_lines.append(cleaned)

    fixed = "".join(cleaned_lines)

    # Replace comparisons with None using Python's recommended identity test.
    updated = re.sub(
        r"==\s*None\b",
        "is None",
        fixed
    )

    if updated != fixed:
        changes.append(
            "Replaced '== None' with the recommended 'is None'."
        )

    fixed = updated

    return fixed, changes


# -----------------------------------------
# MAIN ANALYZER
# -----------------------------------------

def analyze_python_code(code):

    tree, syntax_issue = check_syntax(code)

    if syntax_issue:

        fixed_code, changes = generate_fixed_code(code)

        return {
            "success": False,
            "message": (
                f"{syntax_issue['category']} on line "
                f"{syntax_issue['line']}: {syntax_issue['message']}"
            ),
            "issues": [syntax_issue],
            "summary": {
                "errors": 1,
                "warnings": 0,
                "information": 0
            },
            "statistics": None,
            "loops": [],
            "fixed_code": fixed_code,
            "fixes": changes
        }

    variables = collect_variable_types(tree)

    issues = []

    issues.extend(check_zero_division(tree))
    issues.extend(check_type_errors(tree, variables))
    issues.extend(check_undefined_names(code))

    loop_issues, loops = check_loops(tree)
    issues.extend(loop_issues)

    issues.extend(check_style(code, tree))

    issues.sort(key=lambda item: item["line"])

    errors = sum(
        issue["severity"] == "error" for issue in issues
    )

    warnings = sum(
        issue["severity"] == "warning" for issue in issues
    )

    information = sum(
        issue["severity"] == "info" for issue in issues
    )

    if errors:
        message = f"Analysis completed: {errors} error(s) detected."

    elif warnings:
        message = (
            f"No critical errors detected, but "
            f"{warnings} warning(s) found."
        )

    elif information:
        message = (
            "No critical errors detected. "
            f"{information} style suggestion(s) available."
        )

    else:
        message = "No detected problems!"

    fixed_code, fixes = generate_fixed_code(code)

    return {
        "success": errors == 0,
        "message": message,
        "issues": issues,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "information": information
        },
        "statistics": get_statistics(code, tree),
        "loops": loops,
        "fixed_code": fixed_code,
        "fixes": fixes
    }


# -----------------------------------------
# WEBSITE ROUTES
# -----------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/style.css")
def css():
    return send_from_directory(".", "style.css")


@app.route("/script.js")
def javascript():
    return send_from_directory(".", "script.js")


@app.route("/api/health")
def health():

    return jsonify({
        "status": "online",
        "name": "Code Assistant AI",
        "analyzer": "Advanced Python Static Analyzer"
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Invalid request.",
            "issues": []
        }), 400

    code = data.get("code", "")

    if not isinstance(code, str):
        return jsonify({
            "success": False,
            "message": "Code must be text.",
            "issues": []
        }), 400

    if not code.strip():
        return jsonify({
            "success": False,
            "message": "Please enter Python code.",
            "issues": []
        }), 400

    if len(code) > MAX_CODE_SIZE:
        return jsonify({
            "success": False,
            "message": "Code is too large. Maximum size is 30000 characters.",
            "issues": []
        }), 413

    try:
        return jsonify(analyze_python_code(code))

    except Exception:
        app.logger.exception("Unexpected analyzer error")

        return jsonify({
            "success": False,
            "message": "An unexpected analysis error occurred.",
            "issues": []
        }), 500


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5055,
        debug=False,
        use_reloader=False
    )
