from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

OUTPUT = Path(__file__).resolve().parents[1] / "acceptance" / "samples"

SAMPLES = (
    (
        "01-人事管理制度.docx",
        "员工培训管理制度",
        "人事制度",
        (
            ("适用范围", "本制度适用于单位内部员工的岗前培训和年度继续教育。"),
            ("培训安排", "综合部门每年制定培训计划，记录培训主题、参加人员和完成情况。"),
            ("资料管理", "培训资料由经办人员整理后归档，供内部查询和引用。"),
        ),
    ),
    (
        "02-财务报销办法.docx",
        "差旅费用报销办法",
        "财务制度",
        (
            ("报销范围", "差旅费包括交通费、住宿费和按规定发放的出差补助。"),
            ("提交要求", "报销人应提交审批记录和有效票据，并注明出差事由。"),
            ("审核流程", "部门负责人确认后交财务复核，资料完整后办理报销。"),
        ),
    ),
    (
        "03-项目会议纪要.docx",
        "资料管理项目会议纪要",
        "项目资料",
        (
            ("会议议题", "讨论离线文档导入、正文搜索、分类管理和诊断日志方案。"),
            ("会议决定", "文件导入资料库时采用复制方式，一个文档只属于一个分类。"),
            ("后续事项", "使用虚构材料开展验收，不在诊断包中记录文件名和正文。"),
        ),
    ),
    (
        "04-普通工作通知.docx",
        "办公区域调整通知",
        "综合通知",
        (
            ("调整时间", "办公区域调整工作定于本月最后一个工作日进行。"),
            ("注意事项", "请提前整理个人物品，公共资料统一装箱并做好编号。"),
            ("联系事项", "如有设备搬运需求，请与综合部门联系。"),
        ),
    ),
)


def set_run_font(run, size: int, *, bold: bool = False) -> None:
    run.font.name = "Noto Sans CJK SC"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = None


def create_sample(filename: str, title: str, category: str, sections) -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.4)
    section.left_margin = Cm(2.6)
    section.right_margin = Cm(2.6)

    title_paragraph = document.add_paragraph(style="Title")
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(title_paragraph.add_run(title), 20, bold=True)

    intro = document.add_paragraph()
    intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(intro.add_run(f"模拟验收资料  建议分类 {category}"), 10)

    for heading, body in sections:
        heading_paragraph = document.add_paragraph(style="Heading 1")
        set_run_font(heading_paragraph.add_run(heading), 14, bold=True)
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.line_spacing = 1.5
        paragraph.paragraph_format.first_line_indent = Cm(0.74)
        set_run_font(paragraph.add_run(body), 11)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(footer.add_run("仅用于文澜资料库离线验收"), 9)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT / filename)


def main() -> None:
    for sample in SAMPLES:
        create_sample(*sample)


if __name__ == "__main__":
    main()
