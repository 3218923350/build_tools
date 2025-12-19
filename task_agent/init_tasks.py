import json
import uuid
import os
import pymysql

MYSQL_CONFIG = {
    "host": os.environ["MYSQL_HOST"],
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ["MYSQL_USER"],
    "password": os.environ["MYSQL_PASSWORD"],
    "database": os.environ["MYSQL_DATABASE"],
    "charset": "utf8mb4",
}

MAX_TOOLS = 100

def main():
    with open("../tools/deepmodeling/deepmodeling.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    tools = data["tools"][:MAX_TOOLS]

    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO tool_build_tasks (
            task_id,
            tool_name,
            repo_url,
            status
        ) VALUES (%s, %s, %s, 'pending')
    """

    for tool in tools:
        cursor.execute(
            insert_sql,
            (
                str(uuid.uuid4()),
                tool["name"],
                tool.get("repo_url"),
            )
        )

    conn.commit()

    # 验证一下自增 id
    cursor.execute("""
        SELECT tool_id, tool_name
        FROM tool_build_tasks
        ORDER BY tool_id DESC
        LIMIT %s
    """, (len(tools),))

    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()

    print(f"✅ 成功插入 {len(tools)} 条任务（tool_id 由数据库生成）")

if __name__ == "__main__":
    main()
