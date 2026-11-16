from paper_agent.methodology_composing_using_template import methodology_composing
from paper_agent.related_work_composing_using_template import related_work_composing
from paper_agent.experiments_composing import experiments_composing
from paper_agent.introduction_composing import introduction_composing
from paper_agent.conclusion_composing import conclusion_composing
from paper_agent.abstract_composing import abstract_composing
import asyncio
import argparse
import global_state
from paper_agent.writing_fix import clean_tex_files_in_folder, process_tex_file
from paper_agent.tex_writer import compile_latex_project

async def writing(research_field: str, instance_id: str):
    global_state.report_progress(10, "撰写论文方法", "生成方法章节")
    await methodology_composing(research_field, instance_id)
    global_state.report_progress(25, "撰写相关工作", "生成相关工作章节")
    await related_work_composing(research_field, instance_id)
    global_state.report_progress(40, "整理实验章节", "生成实验章节")
    await experiments_composing(research_field, instance_id)
    global_state.report_progress(55, "撰写论文引言", "生成引言章节")
    await introduction_composing(research_field, instance_id)
    global_state.report_progress(68, "撰写论文结论", "生成结论章节")
    await conclusion_composing(research_field, instance_id)
    global_state.report_progress(78, "撰写论文摘要", "生成摘要章节")
    await abstract_composing(research_field, instance_id)

    target_folder = f"{research_field}/target_sections/{instance_id}"
    global_state.report_progress(88, "整理论文文件", "清理章节文件并处理 BibTeX 引用")
    clean_tex_files_in_folder(target_folder)

    tex_file_path = f'{research_field}/target_sections/{instance_id}/related_work.tex'
    bib_file_path = f'{research_field}/target_sections/{instance_id}/iclr2025_conference.bib'
    process_tex_file(tex_file_path, bib_file_path)

    project_directory = f'{research_field}/target_sections/{instance_id}'
    main_file = "iclr2025_conference.tex"
    global_state.report_progress(95, "编译论文", "正在编译 LaTeX 项目")
    compile_latex_project(project_directory, main_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--research_field", type=str, default="vq")
    parser.add_argument("--instance_id", type=str, default="rotation_vq")
    args = parser.parse_args()
    asyncio.run(writing(args.research_field, args.instance_id))

        