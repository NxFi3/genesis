extends RefCounted
## Shared slate / parchment palette; no fonts or external art dependencies.
const INK := Color("e7eadb")
const MUTED := Color("a2b4ad")
const GOLD := Color("e0bd7c")
const TEAL := Color("89c5b3")

static func box(color: Color, border := Color("3d504c"), radius := 6, margin := 8) -> StyleBoxFlat:
    var style := StyleBoxFlat.new()
    style.bg_color = color
    style.border_color = border
    style.set_border_width_all(1)
    style.set_corner_radius_all(radius)
    style.content_margin_left = margin
    style.content_margin_right = margin
    style.content_margin_top = margin
    style.content_margin_bottom = margin
    return style

static func make_theme() -> Theme:
    var theme := Theme.new()
    theme.default_font_size = 14
    for type in ["Label", "Button", "OptionButton", "CheckBox", "LineEdit", "TextEdit", "SpinBox", "RichTextLabel", "TabContainer"]:
        theme.set_color("font_color", type, INK)
        theme.set_color("font_hover_color", type, Color.WHITE)
        theme.set_color("font_disabled_color", type, Color("788780"))
    theme.set_color("default_color", "RichTextLabel", INK)
    theme.set_color("font_placeholder_color", "TextEdit", MUTED)
    theme.set_color("caret_color", "TextEdit", GOLD)
    for type in ["Button", "OptionButton", "LineEdit", "TextEdit"]:
        theme.set_stylebox("normal", type, box(Color("253833")))
        theme.set_stylebox("hover", type, box(Color("344d44"), TEAL))
        theme.set_stylebox("pressed", type, box(Color("476356"), GOLD))
        theme.set_stylebox("disabled", type, box(Color("202e2a")))
        theme.set_stylebox("focus", type, box(Color(0,0,0,0), GOLD))
    theme.set_stylebox("panel", "TabContainer", box(Color("1c2c29"), Color("40544b"), 5, 12))
    theme.set_stylebox("tab_selected", "TabContainer", box(Color("3c5549"), TEAL))
    theme.set_stylebox("tab_unselected", "TabContainer", box(Color("24362f")))
    theme.set_stylebox("tab_hovered", "TabContainer", box(Color("31473e")))
    theme.set_stylebox("panel", "PopupPanel", box(Color("1c2c29"), TEAL, 10, 16))
    theme.set_stylebox("panel", "PopupMenu", box(Color("22362d")))
    theme.set_stylebox("hover", "PopupMenu", box(Color("476356")))
    theme.set_stylebox("panel", "TooltipPanel", box(Color("17241f"), GOLD))
    return theme

static func safe(value: Variant) -> String:
    return str(value).replace("[", "[lb]")

static func heading(value: String) -> String:
    return "[color=#e0bd7c][b]%s[/b][/color]\n" % safe(value)

static func goods(inventory: Dictionary) -> String:
    var lines: Array[String] = []
    for kind in inventory:
        if float(inventory[kind])<.005: continue
        lines.append("%-12s  %5.1f" % [str(kind).capitalize(), float(inventory[kind])])
    return "[code]%s[/code]" % safe("\n".join(lines))
