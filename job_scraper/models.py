from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    """统一的职位数据结构，所有平台爬取后都转换成这个格式"""

    title: str           # 职位名称
    company: str         # 公司名称
    location: str        # 工作地点
    platform: str        # 来源平台（如 SEEK、Boss直聘）
    url: str             # 职位链接
    job_id: str          # 平台内部 ID（用于去重）
    posted_date: str     # 发布日期（字符串）
    description: str = ""       # 职位描述摘要
    salary: str = ""            # 薪资（如有）
    visa_friendly: str = "unknown"  # "yes" / "no" / "unknown"
    scraped_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    def display(self) -> str:
        """格式化打印，方便在终端查看"""
        lines = [
            f"{'='*60}",
            f"  职位：{self.title}",
            f"  公司：{self.company}",
            f"  地点：{self.location}",
            f"  平台：{self.platform}",
            f"  薪资：{self.salary or '未注明'}",
            f"  发布：{self.posted_date}",
            f"  链接：{self.url}",
        ]
        if self.description:
            lines.append(f"  简介：{self.description[:120]}...")
        return "\n".join(lines)
