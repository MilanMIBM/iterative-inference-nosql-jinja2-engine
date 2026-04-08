# Jinja2 Syntax Cheatsheet

## Delimiters

| Delimiter     | Purpose                                             |
| ------------- | --------------------------------------------------- |
| `{{ ... }}`   | Expressions (output variables/values)               |
| `{% ... %}`   | Statements (control flow, logic)                    |
| `{# ... #}`   | Comments (not rendered)                             |
| `{{- ... -}}` | Whitespace trimming (remove surrounding whitespace) |

---

## Variables

```jinja2
{{ name }}                    {# Simple variable #}
{{ user.name }}               {# Attribute access (dot notation) #}
{{ user['name'] }}            {# Attribute access (subscript notation) #}
{{ items[0] }}                {# List index access #}
```

### Setting Variables

```jinja2
{% set my_var = 'value' %}
{% set my_list = [1, 2, 3] %}
{% set my_dict = {'key': 'value'} %}
```

---

## Control Structures

### If / Elif / Else

```jinja2
{% if condition %}
    ...
{% elif other_condition %}
    ...
{% else %}
    ...
{% endif %}
```

### Ternary Operator

```jinja2
{{ 'yes' if flag else 'no' }}
{{ value if value is defined else 'default' }}
```

### For Loops

```jinja2
{% for item in items %}
    {{ item }}
{% endfor %}

{% for key, value in my_dict.items() %}
    {{ key }}: {{ value }}
{% endfor %}

{% for i in range(5) %}
    {{ i }}
{% endfor %}

{% for item in items %}
    {{ item }}
{% else %}
    No items found.
{% endfor %}
```

### Loop Variables

| Variable              | Description                        |
| --------------------- | ---------------------------------- |
| `loop.index`          | Current iteration (1-indexed)      |
| `loop.index0`         | Current iteration (0-indexed)      |
| `loop.revindex`       | Iterations remaining (1-indexed)   |
| `loop.revindex0`      | Iterations remaining (0-indexed)   |
| `loop.first`          | `True` if first iteration          |
| `loop.last`           | `True` if last iteration           |
| `loop.length`         | Total number of items              |
| `loop.cycle(a, b, c)` | Cycle through values               |
| `loop.depth`          | Nesting level (starts at 1)        |
| `loop.previtem`       | Previous item (undefined on first) |
| `loop.nextitem`       | Next item (undefined on last)      |

---

## Filters

Syntax: `{{ variable | filter }}` or `{{ variable | filter(arg) }}`

### String Filters

| Filter              | Description                        | Example                                        |
| ------------------- | ---------------------------------- | ---------------------------------------------- |
| `upper`             | Uppercase                          | `{{ "hello" \| upper }}` → `HELLO`             |
| `lower`             | Lowercase                          | `{{ "HELLO" \| lower }}` → `hello`             |
| `capitalize`        | Capitalize first char              | `{{ "hello" \| capitalize }}` → `Hello`        |
| `title`             | Title Case                         | `{{ "hello world" \| title }}` → `Hello World` |
| `trim`              | Remove leading/trailing whitespace | `{{ "  hi  " \| trim }}` → `hi`                |
| `striptags`         | Remove HTML/XML tags               | `{{ "<p>hi</p>" \| striptags }}` → `hi`        |
| `replace(old, new)` | Replace substring                  | `{{ "hello" \| replace("l", "x") }}` → `hexxo` |
| `truncate(n)`       | Truncate to n chars                | `{{ "hello world" \| truncate(5) }}`           |
| `wordwrap(n)`       | Wrap at n characters               | `{{ text \| wordwrap(80) }}`                   |
| `center(n)`         | Center in field of width n         | `{{ "hi" \| center(10) }}`                     |
| `format(args)`      | Printf-style formatting            | `{{ "%s - %d" \| format("hi", 5) }}`           |

### List/Iterable Filters

| Filter                   | Description             | Example                                        |
| ------------------------ | ----------------------- | ---------------------------------------------- |
| `length` / `count`       | Get length              | `{{ [1,2,3] \| length }}` → `3`                |
| `first`                  | First element           | `{{ [1,2,3] \| first }}` → `1`                 |
| `last`                   | Last element            | `{{ [1,2,3] \| last }}` → `3`                  |
| `random`                 | Random element          | `{{ [1,2,3] \| random }}`                      |
| `reverse`                | Reverse                 | `{{ [1,2,3] \| reverse \| list }}`             |
| `sort`                   | Sort ascending          | `{{ [3,1,2] \| sort }}`                        |
| `sort(reverse=true)`     | Sort descending         | `{{ [1,2,3] \| sort(reverse=true) }}`          |
| `unique`                 | Remove duplicates       | `{{ [1,1,2] \| unique \| list }}`              |
| `join(sep)`              | Join with separator     | `{{ [1,2,3] \| join(", ") }}` → `1, 2, 3`      |
| `list`                   | Convert to list         | `{{ "abc" \| list }}` → `['a','b','c']`        |
| `batch(n)`               | Split into batches of n | `{{ [1,2,3,4,5] \| batch(2) \| list }}`        |
| `slice(n)`               | Split into n pieces     | `{{ [1,2,3,4,5] \| slice(2) \| list }}`        |
| `map(attr)`              | Extract attribute       | `{{ users \| map(attribute='name') \| list }}` |
| `select(test)`           | Filter by test          | `{{ [1,2,3,4] \| select('even') \| list }}`    |
| `reject(test)`           | Reject by test          | `{{ [1,2,3,4] \| reject('even') \| list }}`    |
| `selectattr(attr, test)` | Filter objects by attr  | `{{ users \| selectattr('active') \| list }}`  |
| `rejectattr(attr, test)` | Reject objects by attr  | `{{ users \| rejectattr('active') \| list }}`  |
| `groupby(attr)`          | Group by attribute      | `{{ users \| groupby('city') }}`               |

### Number Filters

| Filter     | Description         | Example                              |
| ---------- | ------------------- | ------------------------------------ |
| `abs`      | Absolute value      | `{{ -5 \| abs }}` → `5`              |
| `round(n)` | Round to n decimals | `{{ 3.14159 \| round(2) }}` → `3.14` |
| `int`      | Convert to integer  | `{{ "42" \| int }}` → `42`           |
| `float`    | Convert to float    | `{{ "3.14" \| float }}` → `3.14`     |

### Default/Safe Filters

| Filter                    | Description          | Example                              |
| ------------------------- | -------------------- | ------------------------------------ |
| `default(val)` / `d(val)` | Default if undefined | `{{ x \| default('N/A') }}`          |
| `default(val, true)`      | Default if falsy     | `{{ "" \| default('empty', true) }}` |
| `safe`                    | Mark as safe HTML    | `{{ html_content \| safe }}`         |
| `escape` / `e`            | HTML escape          | `{{ "<script>" \| e }}`              |
| `forceescape`             | Force HTML escape    | `{{ content \| forceescape }}`       |

### Data Conversion Filters

| Filter     | Description             | Example                        |
| ---------- | ----------------------- | ------------------------------ |
| `tojson`   | Convert to JSON         | `{{ data \| tojson }}`         |
| `string`   | Convert to string       | `{{ 123 \| string }}`          |
| `dictsort` | Sort dict by key/value  | `{{ mydict \| dictsort }}`     |
| `items`    | Get dict items iterator | `{% for k, v in d \| items %}` |

### Filter Chaining

```jinja2
{{ "  hello world  " | trim | upper }}          {# HELLO WORLD #}
{{ users | selectattr('active') | map(attribute='name') | join(', ') }}
```

---

## Tests

Syntax: `{% if variable is test %}` or `{% if variable is test(arg) %}`

### Type Tests

| Test        | Description     | Example                   |
| ----------- | --------------- | ------------------------- |
| `defined`   | Is defined      | `{% if x is defined %}`   |
| `undefined` | Is undefined    | `{% if x is undefined %}` |
| `none`      | Is None         | `{% if x is none %}`      |
| `boolean`   | Is boolean      | `{% if x is boolean %}`   |
| `true`      | Is True         | `{% if x is true %}`      |
| `false`     | Is False        | `{% if x is false %}`     |
| `string`    | Is string       | `{% if x is string %}`    |
| `number`    | Is number       | `{% if x is number %}`    |
| `integer`   | Is integer      | `{% if x is integer %}`   |
| `float`     | Is float        | `{% if x is float %}`     |
| `mapping`   | Is dict/mapping | `{% if x is mapping %}`   |
| `sequence`  | Is sequence     | `{% if x is sequence %}`  |
| `iterable`  | Is iterable     | `{% if x is iterable %}`  |
| `callable`  | Is callable     | `{% if x is callable %}`  |

### Comparison Tests

| Test                       | Description            | Example                  |
| -------------------------- | ---------------------- | ------------------------ |
| `eq` / `equalto` / `==`    | Equal to               | `{% if x is eq(5) %}`    |
| `ne` / `!=`                | Not equal to           | `{% if x is ne(5) %}`    |
| `gt` / `greaterthan` / `>` | Greater than           | `{% if x is gt(5) %}`    |
| `ge` / `>=`                | Greater or equal       | `{% if x is ge(5) %}`    |
| `lt` / `lessthan` / `<`    | Less than              | `{% if x is lt(5) %}`    |
| `le` / `<=`                | Less or equal          | `{% if x is le(5) %}`    |
| `sameas`                   | Same object (identity) | `{% if x is sameas y %}` |
| `in`                       | Is in sequence         | `{% if x is in(list) %}` |

### Numeric Tests

| Test             | Description    | Example                          |
| ---------------- | -------------- | -------------------------------- |
| `even`           | Is even        | `{% if num is even %}`           |
| `odd`            | Is odd         | `{% if num is odd %}`            |
| `divisibleby(n)` | Divisible by n | `{% if num is divisibleby(3) %}` |

### String Tests

| Test      | Description  | Example                 |
| --------- | ------------ | ----------------------- |
| `lower`   | Is lowercase | `{% if s is lower %}`   |
| `upper`   | Is uppercase | `{% if s is upper %}`   |
| `escaped` | Is escaped   | `{% if s is escaped %}` |

---

## Template Inheritance

### Base Template (base.html)

```jinja2
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Default Title{% endblock %}</title>
</head>
<body>
    <header>{% block header %}{% endblock %}</header>
    <main>{% block content %}{% endblock %}</main>
    <footer>{% block footer %}© 2024{% endblock %}</footer>
</body>
</html>
```

### Child Template (page.html)

```jinja2
{% extends "base.html" %}

{% block title %}My Page{% endblock %}

{% block content %}
    <p>This is my content.</p>
    {{ super() }}  {# Include parent block content #}
{% endblock %}
```

---

## Includes and Imports

### Include

```jinja2
{% include 'header.html' %}
{% include 'sidebar.html' ignore missing %}
{% include 'nav.html' with context %}
{% include 'nav.html' without context %}
```

### Import (Macros)

```jinja2
{% import 'forms.html' as forms %}
{{ forms.input('username') }}

{% from 'forms.html' import input, textarea %}
{{ input('email') }}
```

---

## Macros

### Define a Macro

```jinja2
{% macro input(name, value='', type='text') %}
    <input type="{{ type }}" name="{{ name }}" value="{{ value }}">
{% endmacro %}
```

### Use a Macro

```jinja2
{{ input('username') }}
{{ input('password', type='password') }}
```

### Macro with Caller

```jinja2
{% macro render_dialog(title) %}
    <div class="dialog">
        <h2>{{ title }}</h2>
        <div class="body">{{ caller() }}</div>
    </div>
{% endmacro %}

{% call render_dialog('Hello') %}
    This is the dialog content.
{% endcall %}
```

---

## Whitespace Control

```jinja2
{# No whitespace control #}
{% for i in range(3) %}
    {{ i }}
{% endfor %}

{# With whitespace trimming #}
{%- for i in range(3) -%}
    {{- i -}}
{%- endfor -%}
```

| Syntax | Effect                             |
| ------ | ---------------------------------- |
| `{%-`  | Strip whitespace before tag        |
| `-%}`  | Strip whitespace after tag         |
| `{{-`  | Strip whitespace before expression |
| `-}}`  | Strip whitespace after expression  |

---

## Raw Blocks (Escaping Jinja)

```jinja2
{% raw %}
    This {{ will not }} be {% processed %}
{% endraw %}
```

---

## Line Statements (if enabled)

```jinja2
# for item in items
    {{ item }}
# endfor
```

---

## Operators

### Math

| Operator | Description    |
| -------- | -------------- |
| `+`      | Addition       |
| `-`      | Subtraction    |
| `*`      | Multiplication |
| `/`      | Division       |
| `//`     | Floor division |
| `%`      | Modulo         |
| `**`     | Power          |

### Comparison

| Operator | Description      |
| -------- | ---------------- |
| `==`     | Equal            |
| `!=`     | Not equal        |
| `>`      | Greater than     |
| `>=`     | Greater or equal |
| `<`      | Less than        |
| `<=`     | Less or equal    |

### Logic

| Operator | Description |
| -------- | ----------- |
| `and`    | Logical AND |
| `or`     | Logical OR  |
| `not`    | Logical NOT |
| `(expr)` | Grouping    |

### Other

| Operator | Description          | Example                 |
| -------- | -------------------- | ----------------------- |
| `in`     | Containment          | `{% if x in list %}`    |
| `is`     | Test                 | `{% if x is defined %}` |
| `\|`     | Filter               | `{{ x \| upper }}`      |
| `~`      | String concatenation | `{{ "Hello " ~ name }}` |

---

## Python Usage

```python
from jinja2 import Template, Environment, FileSystemLoader

# Simple rendering
template = Template('Hello {{ name }}!')
result = template.render(name='World')

# From file
env = Environment(loader=FileSystemLoader('templates'))
template = env.get_template('page.html')
result = template.render(title='My Page', items=[1, 2, 3])

# With custom filters
def reverse_string(s):
    return s[::-1]

env.filters['reverse'] = reverse_string
```

---

## Common Patterns

### Check if variable exists and is not empty

```jinja2
{% if items is defined and items | length %}
    {# items exists and has elements #}
{% endif %}
```

### Default with falsy check

```jinja2
{{ value | default('N/A', true) }}
```

### Loop with index

```jinja2
{% for item in items %}
    {{ loop.index }}. {{ item }}
{% endfor %}
```

### Conditional class

```jinja2
<div class="{{ 'active' if is_active else 'inactive' }}">
```

### Building HTML attributes

```jinja2
<ul{{ {'class': class_name, 'id': id_name} | xmlattr }}>
```

### Safe JSON embedding

```jinja2
<script>
    var data = {{ data | tojson | safe }};
</script>
```
