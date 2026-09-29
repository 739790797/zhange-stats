from app.services.minecraft.startup_cmd import (
    assess_command,
    build_args_command,
    build_jar_command,
    core_choices,
    detect_install,
    heap_flags_from_text,
    java_major_for_mc,
    java_warning,
    mc_from_neoforge,
    parse_command,
    suggest_heap_flags,
    suggest_image,
)


def test_neoforge_version_maps_to_minecraft_and_java():
    assert mc_from_neoforge("21.1.248") == "1.21.1"
    assert mc_from_neoforge("20.4.230") == "1.20.4"
    assert java_major_for_mc("1.21.1") == 21
    assert java_major_for_mc("1.20.1") == 17
    assert java_major_for_mc("1.16.5") == 8


def test_heap_suggestion_leaves_headroom():
    assert suggest_heap_flags(8192) == "-Xms6G -Xmx6G"
    assert suggest_heap_flags(0) == "-Xms2G -Xmx2G"
    assert heap_flags_from_text("-Xms4G --add-opens java.base/java.lang=ALL-UNNAMED -Xmx4G") == (
        "-Xms4G -Xmx4G"
    )


def test_jar_and_args_commands():
    assert build_jar_command("-Xms4G -Xmx4G", "arclight.jar", "nogui") == (
        "java -Xms4G -Xmx4G -jar arclight.jar nogui"
    )
    assert build_jar_command("-Xms4G -Xmx4G", "paper.jar", "--nogui") == (
        "java -Xms4G -Xmx4G -jar paper.jar --nogui"
    )
    unix = "libraries/net/neoforged/neoforge/21.1.248/unix_args.txt"
    assert build_args_command(unix) == f"java @user_jvm_args.txt @{unix} nogui"
    assert build_args_command("server.jar") == ""


def test_incomplete_until_files_exist():
    ok, why = assess_command("jar", jar="arclight.jar", jar_exists=False, unix_args="", unix_exists=False)
    assert not ok
    assert "jar" in why
    ok, _why = assess_command(
        "jar", jar="arclight.jar", jar_exists=True, unix_args="", unix_exists=False
    )
    assert ok
    ok, why = assess_command("args", jar="", jar_exists=False, unix_args="", unix_exists=False)
    assert not ok
    assert "unix_args" in why


def test_detect_neoforge_pack_offers_hybrids_not_paper():
    unix = "libraries/net/neoforged/neoforge/21.1.248/unix_args.txt"
    detected = detect_install(["mods", "user_jvm_args.txt"], [unix])
    assert detected["loader"] == "neoforge"
    assert detected["launch"] == "args"
    choices = core_choices(detected, "neoforge")
    ids = [row["id"] for row in choices]
    assert ids[0] == "bundled"
    assert "arclight" in ids
    assert "youer" in ids
    assert "paper" not in ids
    assert choices[0]["unix_args"] == unix


def test_detect_arclight_jar_does_not_duplicate_itself():
    detected = detect_install(["arclight-neoforge-1.21.1.jar"], [])
    assert detected["loader"] == "neoforge"
    assert detected["kind"] == "hybrid"
    ids = [row["id"] for row in core_choices(detected, "neoforge")]
    assert ids.count("arclight") == 0
    assert "youer" in ids


def test_parse_both_command_shapes():
    jar = parse_command("java -Xms4G -Xmx4G -jar paper.jar --nogui")
    assert jar["launch"] == "jar"
    assert jar["jar"] == "paper.jar"
    assert jar["jvm"] == "-Xms4G -Xmx4G"
    unix = "libraries/net/neoforged/neoforge/21.1.248/unix_args.txt"
    args = parse_command(f"java @user_jvm_args.txt @{unix} nogui")
    assert args["launch"] == "args"
    assert args["unix_args"] == unix


def test_java_image_suggestion_and_warning():
    images = [
        "ghcr.io/pelican-eggs/yolks:java_17",
        "ghcr.io/pelican-eggs/yolks:java_21",
    ]
    assert suggest_image(images, 21).endswith("java_21")
    assert "Java 17" in java_warning(images[0], 21)
    assert java_warning(images[1], 21) == ""
