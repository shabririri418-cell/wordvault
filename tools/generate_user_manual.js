const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  ImageRun,
  LevelFormat,
  PageBreak,
  PageNumber,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} = require(path.resolve("build/docx-node/node_modules/docx"));

const OUT = path.resolve("dist/arm64/文澜资料库-操作与功能测试手册.docx");
const SCREENSHOT = path.resolve("build/ui-preview.png");
const BLUE = "0C3B4A";
const GREEN = "197663";
const PALE = "EAF2F1";
const GOLD = "E6A23C";
const GRAY = "68757A";
const BORDER = { style: BorderStyle.SINGLE, size: 1, color: "C7D5D8" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const WIDTH = 9026;

const run = (text, options = {}) => new TextRun({ text, font: "Microsoft YaHei", ...options });
const para = (text, options = {}) => new Paragraph({
  spacing: { after: 120, line: 330 },
  ...options,
  children: [run(text, options.run || {})],
});
const heading = (text, level = 1) => new Paragraph({
  heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
  children: [run(text)],
});
const step = (text, reference = "steps") => new Paragraph({
  numbering: { reference, level: 0 },
  spacing: { after: 100, line: 320 },
  children: [run(text)],
});
const bullet = (text) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  spacing: { after: 80, line: 310 },
  children: [run(text)],
});
const note = (label, text, color = PALE) => new Table({
  width: { size: WIDTH, type: WidthType.DXA },
  columnWidths: [WIDTH],
  rows: [new TableRow({ children: [new TableCell({
    width: { size: WIDTH, type: WidthType.DXA }, borders: BORDERS,
    shading: { fill: color, type: ShadingType.CLEAR },
    margins: { top: 140, bottom: 140, left: 180, right: 180 },
    children: [new Paragraph({ children: [run(label + "：", { bold: true, color: BLUE }), run(text)] })],
  })] })],
});

function cell(text, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA }, borders: BORDERS,
    verticalAlign: VerticalAlign.CENTER,
    shading: opts.header ? { fill: BLUE, type: ShadingType.CLEAR } : opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 90, bottom: 90, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [run(text, { bold: !!opts.header, color: opts.header ? "FFFFFF" : "1E3035", size: opts.header ? 19 : 18 })],
    })],
  });
}

function checklist(rows) {
  const widths = [900, 1830, 3100, 1400, 1796];
  return new Table({
    width: { size: WIDTH, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: [
        cell("编号", widths[0], { header: true, center: true }),
        cell("测试项目", widths[1], { header: true }),
        cell("预期结果", widths[2], { header: true }),
        cell("结果", widths[3], { header: true, center: true }),
        cell("现象/备注", widths[4], { header: true }),
      ]}),
      ...rows.map((r, i) => new TableRow({ children: [
        cell(r[0], widths[0], { center: true, fill: i % 2 ? "F5F8F8" : undefined }),
        cell(r[1], widths[1], { fill: i % 2 ? "F5F8F8" : undefined }),
        cell(r[2], widths[2], { fill: i % 2 ? "F5F8F8" : undefined }),
        cell("□通过\n□失败", widths[3], { center: true, fill: i % 2 ? "F5F8F8" : undefined }),
        cell("", widths[4], { fill: i % 2 ? "F5F8F8" : undefined }),
      ]})),
    ],
  });
}

const children = [];
children.push(
  new Paragraph({ spacing: { before: 700, after: 260 }, alignment: AlignmentType.CENTER, children: [run("文澜资料库", { bold: true, size: 48, color: BLUE })] }),
  new Paragraph({ spacing: { after: 220 }, alignment: AlignmentType.CENTER, children: [run("操作与功能测试手册", { bold: true, size: 34, color: GREEN })] }),
  new Paragraph({ spacing: { after: 700 }, alignment: AlignmentType.CENTER, children: [run("银河麒麟 ARM64／飞腾电脑离线版", { size: 22, color: GRAY })] }),
  note("用途", "本手册既用于日常操作，也用于首次交付测试。请按编号依次测试，在表格中勾选结果；遇到问题时记录测试编号，并导出诊断包。"),
  para("客户单位：________________________", { spacing: { before: 500, after: 180 } }),
  para("测试人员：________________________"),
  para("测试日期：________年____月____日"),
  para("软件版本：0.1.0（首次交付测试版）"),
  new Paragraph({ spacing: { before: 700 }, alignment: AlignmentType.CENTER, children: [run("保密提醒：请勿向开发方发送真实文档、正文、文件名、文件路径或含涉密内容的截图。", { bold: true, color: "A33B2E", size: 20 })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

children.push(
  heading("1. 安装与首次启动"),
  heading("1.1 安装程序", 2),
  step("将“文澜资料库-银河麒麟ARM64-双击安装.tar.gz”完整复制到客户电脑。"),
  step("右键压缩包并选择“解压到当前文件夹”或同类选项。不要在压缩包内部直接运行。"),
  step("打开解压后的“文澜资料库-双击安装”文件夹，双击“安装文澜资料库”图标。"),
  step("出现授权窗口时输入本机管理员密码并确认。安装完成后程序会自动启动。"),
  note("安装失败怎么办", "不要反复修改系统。请保留同目录生成的“安装结果.txt”，记下屏幕提示；可以拍摄不含业务资料的安装提示画面。", "FFF3DC"),
  heading("1.2 选择资料库位置", 2),
  step("首次启动会出现“选择资料库保存位置”。选择一个空间充足、长期不会删除或拔出的本机磁盘目录。"),
  step("程序会在所选位置自动建立“文澜资料库”文件夹。以后文档将复制到这里统一管理。"),
  note("重要", "导入采用“复制”方式，原始 Word 文件仍保留。不要把资料库放在临时目录、U盘或网络盘。程序不代替单位备份制度。", "FFF3DC"),
  heading("1.3 主界面认识", 2),
);
if (fs.existsSync(SCREENSHOT)) {
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 100, after: 90 },
    children: [new ImageRun({
      type: "png", data: fs.readFileSync(SCREENSHOT), transformation: { width: 660, height: 423 },
      altText: { title: "文澜资料库主界面", description: "左侧分类、中间文档、右侧正文预览", name: "主界面" },
    })],
  }));
}
children.push(
  para("左侧：全部文档、未分类、待复核、回收站和自建分类。中间：文档列表。右侧：正文预览与常用操作。顶部：导入、搜索和筛选。"),
  new Paragraph({ children: [new PageBreak()] }),
);

children.push(
  heading("2. 日常操作"),
  heading("2.1 建立分类", 2),
  step("点击左侧“我的分类”右边的“＋”，输入名称，可建立一级分类。"),
  step("如需子分类：在某个分类名称上单击鼠标右键，选择“新建子分类”。"),
  step("创建时可填写关键词，多个关键词用逗号分隔；也可留空。关键词仅用于本机分类建议。"),
  note("分类规则", "一个文档只能属于一个分类。分类最多三级。删除分类后，其中的文档会回到“未分类”，文档本身不会被删除。"),
  heading("2.2 导入文档", 2),
  step("导入少量文件：点击“导入文档”，可一次选择多个 .doc 或 .docx 文件。"),
  step("批量导入：点击“导入文件夹”，程序会扫描所选文件夹及其子文件夹。"),
  step("如遇同名或相同内容，按提示选择“覆盖”“保留两份”或“取消导入”。不确定时建议选择“保留两份”。"),
  step("导入后先在“未分类”中查看，再用右侧“移动到分类”指定归属。"),
  heading("2.3 搜索、预览与引用", 2),
  step("在顶部搜索框输入文件名或正文中的词语，点击“搜索”或按回车。"),
  step("点击结果，中间选中文档后，右侧显示提取出的正文。"),
  step("需要复制部分内容时，先在预览区拖动选择文字，再点“复制正文”；不选择则复制全部正文。"),
  step("需要注明出处时，点击预览区右上“更多”→“复制并附来源”。"),
  step("需要编辑原文时，点击“用 WPS 打开”。保存后返回本程序，程序会检测变化并更新正文和索引。"),
  heading("2.4 回收站与导出", 2),
  step("选中文档，点击预览区“更多”→“移入回收站”。"),
  step("在左侧“回收站”中选中文档，可从“更多”恢复。"),
  step("“设置与帮助”→“清空回收站”会永久删除资料库中的对应副本，且无法恢复，请谨慎操作。"),
  step("导出单份文档：预览区“更多”→“导出文档”。导出一个分类：选中分类后，顶部“更多”→“导出当前分类”。"),
  new Paragraph({ children: [new PageBreak()] }),
);

children.push(
  heading("3. 首次交付功能测试"),
  note("测试方法", "建议先用少量非涉密测试文档熟悉操作，再用客户自己的真实资料进行兼容性测试。真实资料只在客户电脑本地处理，不发给开发方。"),
  heading("3.1 安装与启动测试", 2),
  checklist([
    ["T01", "一键安装", "双击安装图标后出现授权提示，最终显示安装成功。"],
    ["T02", "应用菜单启动", "关闭程序后，可从银河麒麟应用菜单再次打开。"],
    ["T03", "首次选库", "可选择保存位置并进入主界面；重新打开仍使用原资料库。"],
    ["T04", "完全离线", "断网状态下程序仍能启动、导入、搜索和预览。"],
  ]),
  heading("3.2 导入与文档兼容测试", 2),
  step("准备不少于 10 份本地测试文档，尽量包含：DOCX、旧版 DOC、长文档、带标题、表格、页眉页脚、中英文混排等结构。无需向开发方说明文件名和正文。", "testSteps"),
  step("先记录准备数量，再分别使用“导入文档”和“导入文件夹”。", "testSteps"),
  step("每种结构随机打开 1～2 份，对照 WPS 检查正文是否可读。版式不要求完全一致，重点检查文字是否缺失或乱码。", "testSteps"),
  checklist([
    ["T05", "DOCX 导入", "DOCX 能导入并出现在文档列表。"],
    ["T06", "DOC 导入", "旧版 DOC 能导入；若无法解析，应有明确提示且不影响其他文档。"],
    ["T07", "文件夹导入", "可批量扫描子文件夹；导入数量与实际数量相符。"],
    ["T08", "重复文档", "重复导入时出现处理提示，选择后结果正确。"],
    ["T09", "复杂结构", "标题、段落、表格文字、中英文可读，无大面积乱码或缺失。"],
    ["T10", "失败隔离", "单份异常文档不会导致程序退出，其他文档仍可使用。"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

children.push(
  heading("3.3 分类测试", 2),
  checklist([
    ["T11", "一级分类", "点击“＋”建立的是一级分类。"],
    ["T12", "子分类", "右键分类→“新建子分类”，建立位置正确。"],
    ["T13", "三级限制", "分类最多三级，不能误建到第四级。"],
    ["T14", "单一归属", "文档移动后只出现在一个具体分类中。"],
    ["T15", "删除分类", "删除分类后文档回到“未分类”，文件没有丢失。"],
    ["T16", "推荐分类", "设置关键词后，“推荐分类”能给出建议；无建议时提示清楚。"],
  ]),
  heading("3.4 搜索与预览测试", 2),
  step("从一份文档正文中选择一个较少重复、长度为 4～10 个字的词语，在搜索框输入。", "searchSteps"),
  step("分别测试正文开头、中间和结尾的词语；再测试文件名中的词语。", "searchSteps"),
  step("用“筛选”限制格式、时间或分类，并检查结果。", "searchSteps"),
  checklist([
    ["T17", "文件名搜索", "输入文件名片段可找到对应文档。"],
    ["T18", "正文搜索", "正文开头、中间、结尾的测试词均可命中。"],
    ["T19", "中文搜索", "中文词语搜索结果正确且速度可接受。"],
    ["T20", "组合筛选", "格式、时间和分类筛选能缩小结果。"],
    ["T21", "正文预览", "选中文档后预览出现，文字可选择、滚动。"],
    ["T22", "空结果", "搜索不存在的词时正常显示空结果，程序不报错。"],
  ]),
  heading("3.5 WPS、复制与更新测试", 2),
  checklist([
    ["T23", "WPS 打开", "点击“用 WPS 打开”后，正确文档在本机 WPS 中打开。"],
    ["T24", "复制正文", "选择部分文字后只复制选中部分；未选择时复制全部。"],
    ["T25", "复制并附来源", "粘贴后含正文和来源说明。"],
    ["T26", "修改后更新", "在 WPS 修改并保存，返回程序后预览和搜索索引可更新。"],
  ]),
  new Paragraph({ children: [new PageBreak()] }),
);

children.push(
  heading("3.6 回收、导出与稳定性测试", 2),
  checklist([
    ["T27", "移入回收站", "文档从正常列表消失，在回收站可见。"],
    ["T28", "恢复文档", "恢复后重新出现在原分类或正常列表，并可搜索。"],
    ["T29", "导出文档", "导出的 Word 文件可用 WPS 正常打开。"],
    ["T30", "导出分类", "分类内文件可批量导出；同名文件不会相互覆盖。"],
    ["T31", "重启保持", "关闭并重新启动后，文档、分类和索引仍存在。"],
    ["T32", "连续操作", "连续导入、搜索、分类 30 分钟，无异常退出或明显卡死。"],
  ]),
  heading("4. 出现问题时如何反馈", 1),
  heading("4.1 先记录问题，不发送资料", 2),
  bullet("记录失败的测试编号，例如“T18 正文搜索失败”。"),
  bullet("记录发生时间和操作步骤，例如“16:20，导入文件夹后搜索某词无结果”。"),
  bullet("说明结果类型即可，例如“应有 3 条，实际 0 条”；不要写出真实文件名、路径、分类名或正文。"),
  bullet("如果能重复出现，注明“每次都发生”；如果偶发，注明大致出现次数。"),
  heading("4.2 导出脱敏诊断包", 2),
  step("回到程序主界面，点击左下角“设置与帮助”。", "diagSteps"),
  step("选择“导出诊断包”。", "diagSteps"),
  step("选择保存位置，生成“文澜诊断包.zip”。", "diagSteps"),
  step("将诊断包与测试结果表交给开发方，不要另外附带真实 Word 文档。", "diagSteps"),
  note("诊断包范围", "诊断包包含运行环境、自检结果、脱敏事件和匿名文档结构统计；不包含正文、文件名、文件路径、搜索词、分类名称、剪贴板内容或文档哈希。"),
  heading("4.3 推荐反馈格式", 2),
  para("电脑：银河麒麟桌面操作系统（国防版）V10／飞腾 D2000／ARM64"),
  para("失败编号：________________________"),
  para("发生时间：________________________"),
  para("操作步骤：________________________________________________________"),
  para("预期结果：________________________________________________________"),
  para("实际现象：________________________________________________________"),
  para("是否每次发生：□是  □否，大约____次出现____次"),
  para("是否已附诊断包：□是  □否"),
  new Paragraph({ children: [new PageBreak()] }),
);

children.push(
  heading("5. 最终验收汇总"),
  checklist([
    ["A01", "安装与启动", "T01～T04 全部通过。"],
    ["A02", "导入兼容", "T05～T10 通过，或失败项已有诊断包。"],
    ["A03", "分类功能", "T11～T16 全部通过。"],
    ["A04", "搜索预览", "T17～T22 全部通过。"],
    ["A05", "WPS 与复制", "T23～T26 全部通过。"],
    ["A06", "回收导出稳定性", "T27～T32 全部通过。"],
  ]),
  para("本轮结论：□全部通过  □基本通过，存在非阻断问题  □未通过，需要修复", { spacing: { before: 360, after: 220 }, run: { bold: true } }),
  para("客户测试人员签字：____________________    日期：________年____月____日"),
  para("技术人员复核：________________________    日期：________年____月____日"),
  note("特别说明", "首次测试的目的，是确认客户实际银河麒麟、飞腾和 WPS 环境的兼容性。出现问题并不代表客户操作错误；请保留现场，不要自行重装或删除资料库，先导出诊断包。", "FFF3DC"),
);

const doc = new Document({
  creator: "文澜资料库项目组",
  title: "文澜资料库操作与功能测试手册",
  description: "银河麒麟 ARM64 离线版客户操作和首次交付功能测试手册",
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 20, color: "1E3035" }, paragraph: { spacing: { line: 320 } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Microsoft YaHei", size: 30, bold: true, color: BLUE },
        paragraph: { spacing: { before: 260, after: 160 }, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: GREEN, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Microsoft YaHei", size: 24, bold: true, color: GREEN },
        paragraph: { spacing: { before: 210, after: 110 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    ...["steps", "testSteps", "searchSteps", "diagSteps"].map(reference => ({ reference, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 360 } } } }] })),
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 900, right: 1440, bottom: 900, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: "C7D5D8", space: 5 } },
      children: [run("文澜资料库操作与功能测试手册", { color: GRAY, size: 17 }), run("\t第 ", { color: GRAY, size: 17 }), new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 17, color: GRAY }), run(" 页", { color: GRAY, size: 17 })],
      tabStops: [{ type: "right", position: 9026 }],
    })] }) },
    children,
  }],
});

fs.mkdirSync(path.dirname(OUT), { recursive: true });
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUT, buffer);
  console.log(OUT);
});
