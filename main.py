import sqlite3
from datetime import date
import pandas as pd
import streamlit as st

DB_PATH="tasks.db"
PRIORITIES=["High","Medium","Low"]
PRIORITY_ICON={"High":"🔴","Medium":"🟠","Low":"🟢"}
#----- Database helpers -------
def get_conn():
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    return conn 
def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks(
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT,
                priority    TEXT NOT NULL DEFAULT 'Medium',
                due_date    TEXT,
                done        INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) 
            """
        )
def add_task(title,des,priority,due):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO TASKS (title,description,priority,due_date) VALUES(?,?,?,?)",
            (title,des,priority,due.isoformat() if due else None),
        )
def set_done(task_id,done):
    with get_conn() as conn:
        conn.execute("UPDATE TASKS SET done=? WHERE id=?",(int(done),task_id))
def delete_task(task_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?",(task_id,))
def clear_completed():
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE done=1")
def clear_all():
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks ")
def fetch_tasks(status,priority,search,sort_by):
    query="SELECT * FROM tasks WHERE 1=1"
    params=[]
    if status=="Pending":
        query+=" AND DONE=0"
    elif status=="Completed":
        query+=" AND DONE=1"

    if priority!="All":
        query+=" AND priority = ?"
        params.append(priority)

    if search:
        query+=" AND (title LIKE ? OR description LIKE ?)"
        params+=[f"%{search}%",f"%{search}%"]
    
    order={
        "Due date":" due_date IS NULL,due_date ASC",
        "Priority":" CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END",
        "Newest first":" id DESC",
    }[sort_by]
    query+=f" ORDER BY done ASC,{order}"

    with get_conn() as conn:
        return conn.execute(query,params).fetchall()

#---------UI-------
st.set_page_config(page_title="Task Manager",page_icon='✅',layout="centered")
init_db()

#Sidebar filters
st.sidebar.header("Filters")
status_filter=st.sidebar.radio("Status",["All","Pending","Completed"])
priority_filter=st.sidebar.selectbox("Priority",["All"]+PRIORITIES)
search_text=st.sidebar.text_input("Search")
sort_by=st.sidebar.selectbox("Sort by",["Due date","Priority","Newest first"])
st.sidebar.divider()
if st.sidebar.button("Clear completed tasks"):
    clear_completed()
    st.rerun()
if st.sidebar.button("Clear all tasks"):
    clear_all()
    st.rerun()
st.title("✅ Task Manager")
#Stats
with get_conn() as conn:
    total=conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed=conn.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0]
    overdue=conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE done=0 and due_date IS NOT NULL AND due_date<? ",(date.today().isoformat(),),
    ).fetchone()[0]
c1,c2,c3,c4=st.columns(4)
c1.metric("Total",total)
c2.metric("Pending",total-completed)
c3.metric("Completed",completed)
c4.metric("Overdue",overdue)
if total:
    st.progress(completed/total,text=f"{completed/total:.0%} complete")
#Add task form
with st.expander("➕ Add a new task",expanded=(total==0)):
    with st.form("add task",clear_on_submit=True):
        title=st.text_input("Title")
        description=st.text_area("Description (optional) ")
        col_a,col_b,col_c=st.columns([0.5,0.2,0.3])
        priority=col_a.selectbox("Priority",PRIORITIES,index=1)
        has_due=col_b.checkbox("Set Date")
        due=col_c.date_input("Due date",value=date.today())
        if st.form_submit_button("Add task",type="primary"):
            if title.strip():
                add_task(title.strip(),description.strip(),priority,due if has_due else None)
                st.rerun()
            else:
                st.warning("Please enter a title")
st.divider()
#Task list

tasks=fetch_tasks(status_filter,priority_filter,search_text,sort_by)
if not tasks:
    st.info("No tasks match your filters. Add one above!")
for t in tasks:
    is_overdue=(not t["done"] and t["due_date"] < date.today().isoformat()  )
    row=st.columns([0.10,0.75,0.15])
    # Checkbox toggles completion
    checked=row[0].checkbox("done",value=bool(t["done"]),key=f"chk_{t["id"]}",label_visibility="collapsed")
    if checked!=bool(t["done"]):
        set_done(t["id"],checked)
        st.rerun()
    # Titles+details
    title_md=f"~~{t["title"]}~~" if t["done"] else f"**{t["title"]}**"
    row[1].markdown(f"{PRIORITY_ICON[t["priority"]]} {title_md}")
    meta=[]
    if t["due_date"]:
        meta.append(f"{'⚠ Overdue: ' if is_overdue else '📅'}{t["due_date"]}")
    if t["description"]:
        meta.append(t["description"])
    if meta:
        row[1].caption(" . ".join(meta))
    # Delete
    if row[2].button("🗑",key=f"del_{t["id"]}",help="Delete"):
        delete_task(t["id"])
        st.rerun()
#Export
if tasks:
    st.divider()
    df=pd.DataFrame([dict(r) for r in tasks])
    st.download_button(
        "⬇ Export to CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="tasks.csv",
        mime="text/csv",
)
