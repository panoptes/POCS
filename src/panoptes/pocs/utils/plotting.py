import gc

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from panoptes.utils.images.plot import get_palette, add_colorbar
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


def make_autofocus_plot(output_path,
                        initial_thumbnail,
                        final_thumbnail,
                        initial_focus,
                        final_focus,
                        focus_positions,
                        metrics,
                        merit_function,
                        line_fit=None,
                        plot_title='Autofocus Plot',
                        plot_width=9,  # inches
                        plot_height=18,  # inches
                        ):
    """Make autofocus plots.

    This will make three plots, the top and bottom plots showing the initial and
    final thumbnail, respectively.  The middle plot will contain the scatter plot
    for the `metrics` for the given `focus_positions`.

    Args:
        output_path (str): Path for saving plot.
        initial_thumbnail (np.array): The data for the initial thumbnail.
        final_thumbnail (np.array): The data for the final thumbnail.
        initial_focus (int): The initial focus position.
        final_focus (int): The final focus position.
        focus_positions (np.array): An array of `int` corresponding the focus positions.
        metrics (np.array): An array of `float` corresponding to the measured metrics.
        merit_function (str): The name of the merit function used to produce the metrics.
        line_fit (tuple(np.array, np.array)): A tuple for the fitted line. The
            first entry should be an array of `int` used to calculate fit, the second
            entry should be an array of the fitted values.
        plot_title (str): Title to use for plot
        plot_width (int): The plot width in inches.
        plot_height (int): The plot height in inches.

    Returns:
        str: Full path the saved plot.
    """
    fig, axes = plt.subplots(3, 1)
    fig.set_size_inches(plot_width, plot_height)

    # Initial thumbnail.
    ax0 = axes[0]
    im0 = ax0.imshow(initial_thumbnail, interpolation='none', cmap=get_palette(), norm=LogNorm())
    add_colorbar(im0)
    ax0.set_title(f'Initial focus position: {initial_focus}')

    # Focus positions scatter plot.
    ax1 = axes[1]
    ax1.plot(focus_positions, metrics, 'bo', label=f'{merit_function}')
    # Line fit.
    if line_fit:
        ax1.plot(line_fit[0], line_fit[1], 'b-', label='Polynomial fit')

    # ax1.set_xlim(focus_positions[0] - focus_step / 2, focus_positions[-1] + focus_step / 2)
    u_limit = max(0.90 * metrics.max(), 1.10 * metrics.max())
    l_limit = min(0.95 * metrics.min(), 1.05 * metrics.min())
    ax1.set_ylim(l_limit, u_limit)
    ax1.vlines(initial_focus, l_limit, u_limit, colors='k', linestyles=':', label='Initial focus')
    ax1.vlines(final_focus, l_limit, u_limit, colors='k', linestyles='--', label='Best focus')

    ax1.set_xlabel('Focus position')
    ax1.set_ylabel('Focus metric')

    ax1.set_title(plot_title)
    ax1.legend()

    # Final thumbnail plot.
    ax2 = axes[2]
    im2 = ax2.imshow(final_thumbnail, interpolation='none', cmap=get_palette(), norm=LogNorm())
    add_colorbar(im2)
    ax2.set_title(f'Final focus position: {final_focus}')

    fig.savefig(output_path, transparent=False, bbox_inches='tight')

    # Close, close, close, and close.
    plt.cla()
    plt.clf()
    plt.close(fig)
    gc.collect()

    return output_path
