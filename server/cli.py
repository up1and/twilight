import click

from flask.cli import with_appcontext


@click.group()
def rq_group():
    """RQ management commands."""
    pass

@rq_group.command(context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True,
))
@click.pass_context
@with_appcontext
def worker(ctx):
    """Start an RQ worker with Flask context."""
    from extensions import rq

    # Check for --with-scheduler in extra args
    with_scheduler = '--with-scheduler' in ctx.args
    
    # Get worker from extension with proper context handling
    worker = rq.get_worker('default', 'maintenance')
    worker.work(with_scheduler=with_scheduler)

@rq_group.command()
@with_appcontext
def cron():
    """Start the RQ cron daemon with explicit job registration."""
    from extensions import rq
    from tasks import prune_tasks, prune_syncs
    
    # Get scheduler from extension (explicitly uses the connection)
    cron_scheduler = rq.get_scheduler()

    cron_scheduler.register(
        prune_tasks,
        queue_name='maintenance',
        cron='0 0 * * *'
    )
    cron_scheduler.register(
        prune_syncs,
        queue_name='maintenance',
        cron='30 0 * * *'
    )

    cron_scheduler.start()
